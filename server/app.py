"""API phân loại rác trên Modal cho thùng rác tự phân loại.

Một địa chỉ duy nhất, 3 đường (cùng host nên ESP32 giữ được 1 kết nối keep-alive cho cả 3):
- POST /detect  : ESP32 gửi ảnh JPEG, nhận danh sách vật (label, conf, box)
- GET  /health  : kiểm tra sống, không chạy model; ESP32 gọi để mở kết nối sẵn và giữ ấm
- GET  /config  : bảng nhãn -> ngăn để ESP32 tự quyết định đổ vào ngăn nào

Model phải có sẵn trong Volume `smart-bin-models`: file .onnx và file record .json cùng tên,
lấy từ thư mục models/ của repo aware và upload bằng `modal volume put`.
"""
from __future__ import annotations

import modal

APP_NAME = "smart-bin-api"
MODEL_DIR = "/models"
MODEL_VERSION = "aware-bin-v4-yolo26n-onnx-fp32"  # model phân loại rác v4, 7 nhãn
MAX_BYTES = 500_000  # ảnh ESP32-CAM ở VGA thường nhỏ hơn nhiều
MAX_STORE_BYTES = 5_000_000  # ảnh lỗi "quá lớn" vẫn lưu để tìm lỗi camera, nhưng chặn file quá khổ
IMG_SIZE = 640  # model được export với imgsz=640
CONF_THRESHOLD = 0.25  # server trả mọi vật từ 0,25; ESP32 tự áp ngưỡng chặt hơn từ /config

# Bảng ghép nhãn -> ngăn, ESP32 tải qua /config. Bảng TẠM, chưa chốt (ngăn 3 chưa có nhãn nào)
BIN_CONFIG = {
    "config_version": "2026-11-07-draft",
    # Tên ngăn bằng tiếng Anh không dấu để ESP32 và màn hình hiển thị không lỗi font; UI tự dịch theo số ngăn
    "bins": {"1": "Plastic", "2": "Paper", "3": "Metal", "4": "Other"},
    "label_to_bin": {
        "plastic_bottle": 1, "plastic_container": 1, "plastic_cutlery": 1,
        "paper": 2,
        "paper_cup": 4, "tissue": 4, "food_wrapper": 4,
    },
    "default_bin": 4,  # nhãn lạ, không thấy vật, độ tin cậy thấp -> Khác
    "min_conf": 0.5,  # ngưỡng tạm, chốt lại sau khi đo độ chính xác
}

# Giờ giữ 1 máy luôn thức (giờ Việt Nam). Ngoài giờ về 0 để tiết kiệm, request đầu chờ ~5,7 s
WARM_START_HOUR, WARM_END_HOUR = 7, 22
TIMEZONE = "Asia/Ho_Chi_Minh"

# Hai tính năng cần khoá bí mật do chủ tự tạo trong Modal Secret. Bật lên sau khi đã tạo:
#   smart-bin-auth : BIN_TOKEN               -> /detect và /config đòi header X-Bin-Token
#   smart-bin-r2   : R2_ENDPOINT, R2_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
REQUIRE_TOKEN = True
STORE_SAMPLES = True
# Ảnh lưu ở R2 theo ngày -> nhãn -> giờ để web admin duyệt theo ngày, lọc theo nhãn:
#   samples/2026-11-07/plastic_bottle/143205_<request_id>.jpg + .json   (không thấy vật: nhãn "none")
SAMPLE_PREFIX = "samples"
VN_OFFSET_HOURS = 7  # Việt Nam UTC+7 quanh năm, không đổi giờ mùa hè; máy chủ Modal chạy giờ UTC

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "onnxruntime", "pillow", "numpy", "fastapi[standard]"
)
app = modal.App(APP_NAME, image=image)
vol = modal.Volume.from_name("smart-bin-models", create_if_missing=True)
auth_secrets = [modal.Secret.from_name("smart-bin-auth")] if REQUIRE_TOKEN else []
r2_secrets = [modal.Secret.from_name("smart-bin-r2")] if STORE_SAMPLES else []

# Chỉ import trong container; máy local không cần cài các thư viện này
with image.imports():
    import asyncio
    import hmac
    import io
    import json
    import os
    import time
    import uuid
    from datetime import datetime, timedelta, timezone

    import numpy as np
    import onnxruntime as ort
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from PIL import Image


@app.function(image=modal.Image.debian_slim(python_version="3.12").pip_install("boto3"),
              secrets=r2_secrets, timeout=60)
def store_sample(jpeg: bytes, record: dict) -> None:
    """Lưu ảnh + kết quả lên Cloudflare R2 để huấn luyện lại. Chạy riêng, ESP32 không phải chờ."""
    # Hàm này dùng image riêng (có boto3) nên khối image.imports() ở trên không chạy ở đây
    import json as _json
    import os

    import boto3  # R2 tương thích S3 nên dùng boto3, chỉ trỏ endpoint_url về R2

    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto")
    # Request lỗi (ảnh hỏng, quá lớn, model lỗi) vào thư mục "error"; không thấy vật vào "none"
    label = "error" if record.get("error") else (record["top_label"] or "none")
    hhmmss = record["time"].replace(":", "")
    key = f"{SAMPLE_PREFIX}/{record['date']}/{label}/{hhmmss}_{record['request_id']}"
    bucket = os.environ["R2_BUCKET"]
    # Metadata đi kèm file ảnh: web admin đọc được nhãn, độ tin cậy mà không cần mở file .json
    meta = {"label": label, "conf": str(record["top_conf"]), "model": record["model"],
            "status": str(record["status"])}
    s3.put_object(Bucket=bucket, Key=f"{key}.jpg", Body=jpeg, ContentType="image/jpeg", Metadata=meta)
    s3.put_object(Bucket=bucket, Key=f"{key}.json", Body=_json.dumps(record, ensure_ascii=False).encode(),
                  ContentType="application/json")


@app.cls(
    cpu=(0.25, 0.5),
    memory=(1024, 1536),
    min_containers=1,  # giữ 1 máy thức để không cold start (~5,7 s > hạn 3 s của ESP32); lịch bên dưới tắt ban đêm
    scaledown_window=600,  # giữ máy thêm 10 phút sau request cuối
    max_containers=1,  # chặn chi phí phát sinh nếu bị spam
    volumes={MODEL_DIR: vol},
    secrets=auth_secrets,
    timeout=60,
)
@modal.concurrent(max_inputs=4)
class Detector:
    @modal.enter()
    def load(self):
        self.session = ort.InferenceSession(f"{MODEL_DIR}/{MODEL_VERSION}.onnx")
        self.input_name = self.session.get_inputs()[0].name
        # File record đi kèm model giữ danh sách nhãn đúng thứ tự class_id
        with open(f"{MODEL_DIR}/{MODEL_VERSION}.json") as f:
            self.names = json.load(f)["labels"]
        self.token = os.environ.get("BIN_TOKEN", "")

    def letterbox(self, img: Image.Image):
        # Thu nhỏ giữ nguyên tỉ lệ rồi pad viền xám cho đủ 640x640, để vật không bị méo
        w, h = img.size
        r = min(IMG_SIZE / w, IMG_SIZE / h)
        nw, nh = round(w * r), round(h * r)
        pad_x, pad_y = (IMG_SIZE - nw) / 2, (IMG_SIZE - nh) / 2
        canvas = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (114, 114, 114))
        canvas.paste(img.resize((nw, nh), Image.BILINEAR), (round(pad_x - 0.1), round(pad_y - 0.1)))
        # YOLO chỉ chia 255, KHÔNG trừ mean/std như MobileNet
        x = (np.asarray(canvas, dtype=np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis]
        return x, r, pad_x, pad_y

    def infer(self, img: Image.Image) -> list[dict]:
        x, r, pad_x, pad_y = self.letterbox(img)
        # Đầu ra NMS-free: [1, 300, 6], mỗi dòng = x1, y1, x2, y2, conf, class
        rows = self.session.run(None, {self.input_name: x})[0][0]
        w, h = img.size
        objects = []
        for x1, y1, x2, y2, conf, cls in rows[rows[:, 4] >= CONF_THRESHOLD]:
            # Đổi toạ độ từ ảnh 640x640 đã pad về ảnh gốc
            box = [(x1 - pad_x) / r, (y1 - pad_y) / r, (x2 - pad_x) / r, (y2 - pad_y) / r]
            box = [round(min(max(v, 0), lim)) for v, lim in zip(box, (w, h, w, h))]
            objects.append({"label": self.names[int(cls)], "conf": round(float(conf), 3), "box": box})
        return sorted(objects, key=lambda o: o["conf"], reverse=True)  # vật tin cậy nhất đứng đầu

    def check_token(self, request: Request) -> None:
        # Chưa tạo Secret thì self.token rỗng: bỏ qua kiểm tra (giai đoạn thử)
        if self.token and not hmac.compare_digest(request.headers.get("x-bin-token", ""), self.token):
            raise HTTPException(401, "Missing or invalid X-Bin-Token")

    @modal.asgi_app(label=APP_NAME)
    def api(self):
        web = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None)
        # Trang demo chạy trên trình duyệt gọi từ domain khác nên cần CORS
        web.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type", "X-Bin-Token", "X-Device-Id"])

        @web.get("/health")
        async def health():
            return {"ok": True, "model": MODEL_VERSION, "config_version": BIN_CONFIG["config_version"]}

        @web.get("/config")
        async def config(request: Request):
            self.check_token(request)
            return {"model": MODEL_VERSION, "labels": self.names, **BIN_CONFIG}

        @web.post("/detect")
        async def detect(request: Request, background: BackgroundTasks):
            t0 = time.perf_counter()
            # Sai token -> 401 và KHÔNG lưu, để người lạ không đổ rác vào bucket được
            self.check_token(request)
            body = await request.body()
            t_recv = time.perf_counter()  # nhận xong ảnh qua mạng
            now_vn = datetime.now(timezone(timedelta(hours=VN_OFFSET_HOURS)))
            # Trace log: 1 dòng JSON mỗi request, xem bằng `modal app logs smart-bin-api`
            trace = {
                "event": "detect", "request_id": uuid.uuid4().hex[:12], "model": MODEL_VERSION,
                "device": request.headers.get("x-device-id", ""), "bytes": len(body),
                "date": now_vn.strftime("%Y-%m-%d"), "time": now_vn.strftime("%H:%M:%S"),
                "recv_ms": round((t_recv - t0) * 1000, 1), "top_label": None, "top_conf": 0.0,
            }

            def finish(status: int, payload: dict) -> JSONResponse:
                # Mọi kết quả (thành công hay lỗi) đi qua đây: ghi log, lưu ảnh, trả phản hồi.
                # Phải TRẢ VỀ response chứ không raise HTTPException, vì raise sẽ bỏ qua background task
                trace["status"] = status
                if STORE_SAMPLES and body and len(body) <= MAX_STORE_BYTES:
                    # Chạy SAU khi đã gửi phản hồi cho ESP32: riêng việc giao ảnh cho hàm nền mất 0,3–1,8 s
                    background.add_task(store_sample.spawn.aio, body, trace)
                trace["server_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                print(json.dumps({k: v for k, v in trace.items() if k != "objects"}, ensure_ascii=False))
                return JSONResponse(payload, status_code=status, background=background)

            def fail(status: int, error: str) -> JSONResponse:
                trace["error"] = error
                return finish(status, {"detail": error, "request_id": trace["request_id"]})

            if not body or len(body) > MAX_BYTES:
                return fail(400, "Image is empty or too large")
            try:
                img = Image.open(io.BytesIO(body)).convert("RGB")
            except Exception:
                return fail(400, "Cannot decode JPEG image")
            t1 = time.perf_counter()
            try:
                # Chạy model trong thread riêng để không chặn các request khác đang chờ
                objects = await asyncio.to_thread(self.infer, img)
            except Exception as err:
                return fail(500, f"Inference failed: {type(err).__name__}")
            t2 = time.perf_counter()

            top = objects[0] if objects else {"label": None, "conf": 0.0}
            infer_ms = round((t2 - t1) * 1000, 1)
            trace.update(image_size=list(img.size), decode_ms=round((t1 - t_recv) * 1000, 1),
                         infer_ms=infer_ms, count=len(objects), top_label=top["label"],
                         top_conf=top["conf"], objects=objects)
            return finish(200, {"model": MODEL_VERSION, "request_id": trace["request_id"],
                                "infer_ms": infer_ms, "count": len(objects), "objects": objects,
                                "image_size": list(img.size)})

        return web


def set_warm_containers(n: int) -> None:
    # Đổi số máy luôn thức của bản đang chạy, không cần deploy lại
    modal.Cls.from_name(APP_NAME, "Detector")().update_autoscaler(min_containers=n)


@app.function(schedule=modal.Cron(f"0 {WARM_START_HOUR} * * *", timezone=TIMEZONE))
def warm_up():
    set_warm_containers(1)


@app.function(schedule=modal.Cron(f"0 {WARM_END_HOUR} * * *", timezone=TIMEZONE))
def cool_down():
    set_warm_containers(0)
