import Foundation
import ImageIO
import UniformTypeIdentifiers
// usage: heic2png <src> <dst>; applies the EXIF/HEIF orientation, writes lossless PNG
let a = CommandLine.arguments
guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: a[1]) as CFURL, nil),
      let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any],
      let w = props[kCGImagePropertyPixelWidth] as? Int, let h = props[kCGImagePropertyPixelHeight] as? Int
else { fputs("cannot read \(a[1])\n", stderr); exit(1) }
let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
                             kCGImageSourceCreateThumbnailWithTransform: true,
                             kCGImageSourceThumbnailMaxPixelSize: max(w, h)]
guard let img = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary),
      let dst = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)
else { fputs("cannot convert \(a[1])\n", stderr); exit(1) }
CGImageDestinationAddImage(dst, img, nil)
guard CGImageDestinationFinalize(dst) else { exit(1) }
print("\(props[kCGImagePropertyOrientation] ?? "none") \(img.width)x\(img.height)")
