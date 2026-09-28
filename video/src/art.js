// Vector illustrations and icons. Every function returns SVG markup; ids are
// namespaced per call so the same drawing can appear several times.

(function () {
  "use strict";
  let uid = 0;
  const nid = (p) => `${p}${++uid}`;

  const LEAF_PATH = "M512 273H751V512A239 239 0 0 1 512 751A239 239 0 0 1 273 512A239 239 0 0 1 512 273Z";

  // App icon leaf, drawn in the 1024 icon grid.
  function leaf({ fill = "#468749", vein = "#fff", stem = true, veinKey = "", stemKey = "" } = {}) {
    return `<path d="${LEAF_PATH}" fill="${fill}"/>` +
      (stem ? `<path ${stemKey ? `data-k="${stemKey}"` : ""} d="M352 672L298 726" stroke="${fill}" stroke-width="50" stroke-linecap="round" fill="none"/>` : "") +
      `<path ${veinKey ? `data-k="${veinKey}"` : ""} d="M421 605L546 480" stroke="${vein}" stroke-width="52" stroke-linecap="round" fill="none"/>`;
  }

  // ------------------------------------------------------------------
  // Hero bottle (viewBox 0 0 200 560). Keys let scenes animate parts:
  //   <k>Cap, <k>CapRidges, <k>Level (liquid group, counter-rotated),
  //   <k>Liquid (rect), <k>Crinkle, <k>Vision (machine-vision overlay)
  // ------------------------------------------------------------------
  const BODY = "M70 76L130 76L130 96C130 124 180 140 180 196L180 512C180 530 168 540 150 540L50 540C32 540 20 530 20 512L20 196C20 140 70 124 70 96Z";

  function bottle(k = nid("b"), { level = 0.58, vision = false, crinkle = false } = {}) {
    const g = nid("bg");
    const levelY = 540 - level * 430;
    return `
    <defs>
      <clipPath id="${g}c"><path d="${BODY}"/></clipPath>
      <clipPath id="${g}cap"><rect x="66" y="20" width="68" height="47" rx="7"/></clipPath>
      <linearGradient id="${g}body" x1="20" x2="180" y1="0" y2="0" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="#9ED3EA" stop-opacity=".72"/>
        <stop offset=".1" stop-color="#D9F0FA" stop-opacity=".34"/>
        <stop offset=".3" stop-color="#FFFFFF" stop-opacity=".12"/>
        <stop offset=".58" stop-color="#CFE9F6" stop-opacity=".14"/>
        <stop offset=".84" stop-color="#8CC6E0" stop-opacity=".32"/>
        <stop offset="1" stop-color="#5E9FC0" stop-opacity=".78"/>
      </linearGradient>
      <linearGradient id="${g}liq" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="#9BD9F7" stop-opacity=".55"/>
        <stop offset="1" stop-color="#3F95D0" stop-opacity=".72"/>
      </linearGradient>
      <linearGradient id="${g}cyl" x1="20" x2="180" y1="0" y2="0" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="#000" stop-opacity=".28"/>
        <stop offset=".22" stop-color="#fff" stop-opacity=".22"/>
        <stop offset=".34" stop-color="#fff" stop-opacity=".05"/>
        <stop offset=".78" stop-color="#000" stop-opacity=".06"/>
        <stop offset="1" stop-color="#000" stop-opacity=".32"/>
      </linearGradient>
      <linearGradient id="${g}cap" x1="66" x2="134" y1="0" y2="0" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="#7E0B1B"/><stop offset=".26" stop-color="#D8313F"/>
        <stop offset=".4" stop-color="#F7707A"/><stop offset=".58" stop-color="#D22A3B"/>
        <stop offset="1" stop-color="#7A0A19"/>
      </linearGradient>
      <filter id="${g}soft" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="2.2"/></filter>
      <pattern id="${g}rid" width="5" height="60" patternUnits="userSpaceOnUse"><rect width="1.8" height="60" fill="#000" fill-opacity=".22"/></pattern>
    </defs>
    <g data-k="${k}Squash">
      <g clip-path="url(#${g}c)">
        <rect x="0" y="0" width="200" height="560" fill="url(#${g}body)"/>
        <g data-k="${k}Level"><rect data-k="${k}Liquid" x="-400" y="${levelY}" width="1000" height="800" fill="url(#${g}liq)"/>
          <rect data-k="${k}Surface" x="-400" y="${levelY - 1.5}" width="1000" height="3" fill="#E8F7FF" fill-opacity=".75"/></g>
        <g opacity=".9">
          <rect x="0" y="300" width="200" height="118" fill="#F6F8F6"/>
          <path d="M20 392C70 372 110 404 180 372L180 386C110 418 70 386 20 406Z" fill="#E03A4B"/>
          <path d="M20 318C80 306 120 326 180 312" stroke="#E03A4B" stroke-width="3" fill="none"/>
          <path d="M128 332H140V344A12 12 0 0 1 128 356A12 12 0 0 1 116 344A12 12 0 0 1 128 332Z" fill="#34A862"/>
          <path d="M123 349l8-8" stroke="#fff" stroke-width="2.8" stroke-linecap="round"/>
        </g>
        <rect x="0" y="0" width="200" height="560" fill="url(#${g}cyl)"/>
        <g fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="2">
          <path d="M20 222C60 232 140 232 180 222"/><path d="M20 238C60 248 140 248 180 238"/>
          <path d="M20 470C60 480 140 480 180 470"/>
        </g>
        <path d="M24 522C60 544 140 544 176 522" stroke="#fff" stroke-opacity=".3" stroke-width="3" fill="none"/>
        ${crinkle ? `<g data-k="${k}Crinkle" fill="none" stroke="#5E8FA8" stroke-opacity=".7" stroke-width="3.5" stroke-linejoin="round" opacity="0">
          <path d="M20 260L60 280L90 256L130 284L180 262"/><path d="M20 330L50 350L96 326L140 352L180 330"/>
          <path d="M20 430L64 452L100 426L150 456L180 434"/><path d="M60 280L64 330M130 284L140 352M96 326L100 426"/></g>` : ""}
      </g>
      <path d="${BODY}" fill="none" stroke="#E9F7FF" stroke-opacity=".75" stroke-width="2.4"/>
      <rect x="37" y="190" width="12" height="318" rx="6" fill="#fff" fill-opacity=".62" filter="url(#${g}soft)"/>
      <rect x="152" y="200" width="6" height="300" rx="3" fill="#fff" fill-opacity=".28" filter="url(#${g}soft)"/>
      <path d="M46 170C58 142 78 128 86 104" stroke="#fff" stroke-opacity=".55" stroke-width="6" stroke-linecap="round" fill="none" filter="url(#${g}soft)"/>
      <rect x="61" y="66" width="78" height="11" rx="3" fill="#D9EEF7" fill-opacity=".55" stroke="#fff" stroke-opacity=".5"/>
      <g data-k="${k}Cap">
        <rect x="66" y="20" width="68" height="47" rx="7" fill="url(#${g}cap)"/>
        <g clip-path="url(#${g}cap)"><rect data-k="${k}CapRidges" x="40" y="24" width="120" height="43" fill="url(#${g}rid)"/></g>
        <rect x="66" y="20" width="68" height="7" rx="3.5" fill="#fff" fill-opacity=".28"/>
      </g>
      ${vision ? `<g data-k="${k}Vision" opacity="0">
        <path d="${BODY}" fill="none" stroke="#5BD98A" stroke-width="2" stroke-dasharray="6 7"/>
        <g clip-path="url(#${g}c)" stroke="#5BD98A" stroke-opacity=".45" stroke-width="1.2">
          ${Array.from({ length: 22 }, (_, i) => `<path d="M0 ${110 + i * 20}H200"/>`).join("")}
          ${Array.from({ length: 9 }, (_, i) => `<path d="M${20 + i * 20} 0V560"/>`).join("")}
        </g>
        <g fill="#BFF0CF">${[[70, 76], [130, 76], [20, 196], [180, 196], [20, 512], [180, 512], [100, 540], [66, 20], [134, 20]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="4.5"/>`).join("")}</g>
      </g>` : ""}
    </g>`;
  }

  // ------------------------------------------------------------------
  // Seven classes, viewBox 0 0 200 200, natural colours.
  // ------------------------------------------------------------------
  function itemBottle() {
    return `<svg viewBox="0 0 200 200"><g transform="translate(62 4) scale(.34)">${bottle(nid("ib"), { level: 0.5 })}</g></svg>`;
  }
  function itemJar() {
    const g = nid("jar");
    return `<svg viewBox="0 0 200 200"><defs>
      <linearGradient id="${g}" x1="0" x2="1"><stop offset="0" stop-color="#2F7F63"/><stop offset=".25" stop-color="#6CC49E"/><stop offset=".5" stop-color="#4BA383"/><stop offset="1" stop-color="#23634B"/></linearGradient>
      <linearGradient id="${g}l" x1="0" x2="1"><stop offset="0" stop-color="#8A6A1E"/><stop offset=".35" stop-color="#F0CF6A"/><stop offset=".6" stop-color="#C9A13C"/><stop offset="1" stop-color="#7C5E17"/></linearGradient></defs>
      <rect x="52" y="50" width="96" height="134" rx="26" fill="url(#${g})"/>
      <rect x="58" y="36" width="84" height="22" rx="6" fill="url(#${g}l)"/>
      <g stroke="#6B4F12" stroke-opacity=".35" stroke-width="2">${Array.from({ length: 13 }, (_, i) => `<path d="M${64 + i * 6} 39v16"/>`).join("")}</g>
      <rect x="64" y="72" width="12" height="96" rx="6" fill="#fff" fill-opacity=".45"/>
      <rect x="68" y="98" width="64" height="44" rx="6" fill="#F4EFE2"/>
      <path d="M78 114h44M78 126h30" stroke="#2F7F63" stroke-width="5" stroke-linecap="round"/></svg>`;
  }
  function itemCan() {
    const g = nid("can");
    return `<svg viewBox="0 0 200 200"><defs>
      <linearGradient id="${g}" x1="0" x2="1"><stop offset="0" stop-color="#7C8791"/><stop offset=".2" stop-color="#E7EDF1"/><stop offset=".35" stop-color="#FFFFFF"/><stop offset=".6" stop-color="#B9C3CA"/><stop offset="1" stop-color="#6A747D"/></linearGradient>
      <linearGradient id="${g}b" x1="0" x2="1"><stop offset="0" stop-color="#A2520C"/><stop offset=".3" stop-color="#F29A3F"/><stop offset=".6" stop-color="#E07F24"/><stop offset="1" stop-color="#8F4508"/></linearGradient></defs>
      <path d="M58 46h84v118c0 12-19 20-42 20s-42-8-42-20z" fill="url(#${g})"/>
      <path d="M58 76h84v66H58z" fill="url(#${g}b)"/>
      <path d="M58 142c0 8 19 14 42 14s42-6 42-14" fill="none" stroke="#fff" stroke-opacity=".4" stroke-width="2"/>
      <ellipse cx="100" cy="44" rx="42" ry="12" fill="#D5DDE3" stroke="#8C979F" stroke-width="3"/>
      <ellipse cx="100" cy="44" rx="30" ry="7" fill="#AEB8C0"/>
      <rect x="92" y="36" width="24" height="10" rx="5" fill="#E9EEF1" stroke="#7C8791" stroke-width="2"/>
      <path d="M70 90c10 12 16 30 14 44" stroke="#fff" stroke-opacity=".35" stroke-width="6" stroke-linecap="round" fill="none"/></svg>`;
  }
  function itemBox() {
    return `<svg viewBox="0 0 200 200">
      <path d="M100 30l72 34v78l-72 36-72-36V64z" fill="#B07A43"/>
      <path d="M100 30l72 34-72 34-72-34z" fill="#D8A66A"/>
      <path d="M100 98v80l72-36V64z" fill="#94622F"/>
      <path d="M64 47l72 34v16l-72-34z" fill="#EFD3A1" opacity=".95"/>
      <path d="M136 81v16l-8 4V85z" fill="#E1BE84"/>
      <path d="M46 118l30 15M46 128l20 10" stroke="#7A4F24" stroke-width="3" stroke-linecap="round" opacity=".6"/></svg>`;
  }
  function itemBag() {
    return `<svg viewBox="0 0 200 200">
      <path d="M74 62V50a26 26 0 0 1 52 0v12" fill="none" stroke="#B8A9E8" stroke-width="9" stroke-linecap="round"/>
      <path d="M44 62h112l-8 112a10 10 0 0 1-10 9H62a10 10 0 0 1-10-9z" fill="#E4DDFB" fill-opacity=".92"/>
      <path d="M44 62h112l-4 38H48z" fill="#CFC3F5"/>
      <path d="M70 110l8 60M118 104l-6 68" stroke="#A18FE0" stroke-width="3" stroke-opacity=".6" fill="none"/>
      <path d="M60 80h80" stroke="#fff" stroke-width="4" stroke-opacity=".6"/>
      <circle cx="100" cy="136" r="16" fill="none" stroke="#7B5BC4" stroke-width="4"/>
      <path d="M92 144l16-16" stroke="#7B5BC4" stroke-width="4" stroke-linecap="round"/></svg>`;
  }
  function itemCup() {
    return `<svg viewBox="0 0 200 200">
      <path d="M58 58h84l-12 124H70z" fill="#FBF6EC"/>
      <path d="M62 94h76l-5 50H67z" fill="#C8903D"/>
      <path d="M64 106h72M66 132h68" stroke="#A66A00" stroke-width="3" stroke-opacity=".5"/>
      <rect x="50" y="42" width="100" height="18" rx="8" fill="#F1ECE2" stroke="#D8CFBF" stroke-width="2"/>
      <path d="M62 42c4-10 12-14 38-14s34 4 38 14z" fill="#FFFFFF" stroke="#D8CFBF" stroke-width="2"/>
      <path d="M74 64l6 110" stroke="#fff" stroke-width="6" stroke-opacity=".7" stroke-linecap="round"/></svg>`;
  }
  function itemFoam() {
    return `<svg viewBox="0 0 200 200">
      <path d="M34 104c4-40 30-62 66-62s62 22 66 62z" fill="#F4F6F5"/>
      <path d="M50 96c6-24 24-38 50-38" stroke="#fff" stroke-width="6" stroke-linecap="round" fill="none"/>
      <path d="M26 112h148l-12 50a10 10 0 0 1-10 8H48a10 10 0 0 1-10-8z" fill="#E6EBE8"/>
      <rect x="22" y="102" width="156" height="14" rx="6" fill="#D5DCD8"/>
      <g fill="#C4CCC8">${[[60, 132], [84, 142], [110, 134], [136, 144], [72, 154], [122, 156], [98, 152], [150, 130]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3"/>`).join("")}</g>
      <g fill="#DDE3E0">${[[70, 78], [96, 70], [124, 80], [146, 94], [58, 92]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3"/>`).join("")}</g></svg>`;
  }

  const CLASSES = [
    { key: "bottle", name: "Plastic bottle", tint: "#5BD98A", draw: itemBottle },
    { key: "glass", name: "Glass bottle or jar", tint: "#4CBFD0", draw: itemJar },
    { key: "can", name: "Metal can", tint: "#E08C33", draw: itemCan },
    { key: "box", name: "Cardboard", tint: "#6FA8E0", draw: itemBox },
    { key: "bag", name: "Plastic bag", tint: "#A58BE8", draw: itemBag },
    { key: "cup", name: "Disposable cup", tint: "#E0A23A", draw: itemCup },
    { key: "foam", name: "Styrofoam", tint: "#A9B4AD", draw: itemFoam },
  ];

  // ------------------------------------------------------------------
  // UI icons (24 grid), in the spirit of the SF Symbols the app uses.
  // ------------------------------------------------------------------
  const ICON = {
    house: `<path fill="currentColor" d="M12 3.2l9 7.6h-2.6V20a1 1 0 0 1-1 1h-3.9v-6h-3v6H6.6a1 1 0 0 1-1-1v-9.2H3z"/>`,
    camera: `<path fill="currentColor" d="M8.4 5.2L10 3h4l1.6 2.2H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7.2a2 2 0 0 1 2-2z"/><circle cx="12" cy="12.4" r="3.8" fill="#0B1A11" fill-opacity=".85"/>`,
    photo: `<rect x="3" y="4" width="18" height="16" rx="2.5" fill="currentColor"/><path fill="#0B1A11" fill-opacity=".85" d="M5.5 17.5l4.2-5 3 3.3 2-2.3 3.8 4z"/><circle cx="15.6" cy="8.6" r="1.7" fill="#0B1A11" fill-opacity=".85"/>`,
    leaf: `<path fill="currentColor" d="M12 3h9v9a9 9 0 0 1-9 9 9 9 0 0 1-9-9 9 9 0 0 1 9-9z"/>`,
    trash: `<path fill="currentColor" d="M9 3h6l1 2h4v2H4V5h4zM5.8 8.5h12.4l-1 12a1.6 1.6 0 0 1-1.6 1.5H8.4a1.6 1.6 0 0 1-1.6-1.5z"/>`,
    cloud: `<path fill="currentColor" d="M7 19a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.5 1.5A3.8 3.8 0 0 1 17.5 19z"/>`,
    flag: `<path fill="currentColor" d="M5 3h1.8v18H5zM7.6 4h11l-2.5 4 2.5 4h-11z"/>`,
    flame: `<path fill="currentColor" d="M12 2.5c.6 3-1.2 4.6-2.6 6.2C8 10.3 7 11.9 7 14.3 7 17.9 9.2 21 12 21s5-2.4 5-6c0-3.2-1.9-4.4-2.5-6.6-.4 1.5-1.2 2.4-2 2.8.6-3-.2-6.4-.5-8.7z"/>`,
    bars: `<path fill="currentColor" d="M4 13h4v8H4zM10 5h4v16h-4zM16 9h4v12h-4z"/>`,
    barsx: `<path fill="currentColor" d="M3 20h18v1.5H3zM5 12h2.5v7H5zM9 8h2.5v11H9zM13 11h2.5v8H13zM17 6h2.5v13H17z"/>`,
    pin: `<path fill="currentColor" d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/><circle cx="12" cy="9" r="2.6" fill="#fff"/>`,
    heart: `<path fill="currentColor" d="M12 20.5l-1.3-1.2C5.6 14.7 2.5 11.9 2.5 8.4 2.5 5.6 4.7 3.5 7.4 3.5c1.6 0 3.1.7 4.1 1.9h1c1-1.2 2.5-1.9 4.1-1.9 2.7 0 4.9 2.1 4.9 4.9 0 3.5-3.1 6.3-8.2 10.9z"/>`,
    heartO: `<path fill="none" stroke="currentColor" stroke-width="2" d="M12 20.5l-1.3-1.2C5.6 14.7 2.5 11.9 2.5 8.4 2.5 5.6 4.7 3.5 7.4 3.5c1.6 0 3.1.7 4.1 1.9h1c1-1.2 2.5-1.9 4.1-1.9 2.7 0 4.9 2.1 4.9 4.9 0 3.5-3.1 6.3-8.2 10.9z"/>`,
    bubble: `<path fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" d="M4 6a2.5 2.5 0 0 1 2.5-2.5h11A2.5 2.5 0 0 1 20 6v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4A2.5 2.5 0 0 1 4 14z"/>`,
    bookmark: `<path fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" d="M6.5 3.5h11v17l-5.5-4-5.5 4z"/>`,
    share: `<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M12 3v12M7.5 7.5L12 3l4.5 4.5M5 12v7a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19v-7"/>`,
    recycle: `<g fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M19 11a7 7 0 0 0-12.2-4.2"/><path d="M6 3.5v3.8h3.8"/><path d="M5 13a7 7 0 0 0 12.2 4.2"/><path d="M18 20.5v-3.8h-3.8"/></g>`,
    check: `<path fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.5 4.5L19 7.5"/>`,
    checkc: `<circle cx="12" cy="12" r="10" fill="currentColor"/><path fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" d="M7.5 12.3l3 3 6-6.3"/>`,
    tag: `<path fill="currentColor" d="M3 4.5A1.5 1.5 0 0 1 4.5 3h6.8l9.7 9.7-8.3 8.3L3 11.3zM7.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"/>`,
    magnify: `<circle cx="10.5" cy="10.5" r="6" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M15 15l5 5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M10.5 7.5v6M7.5 10.5h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
    bolt: `<path fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" d="M13.5 2.5L5 13.5h6l-1 8 8.5-11h-6z"/>`,
    sliders: `<g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.2" fill="none"/><circle cx="9" cy="17" r="2.2" fill="none"/></g>`,
    chevron: `<path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>`,
    globe: `<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" fill="none" stroke="currentColor" stroke-width="1.6"/>`,
    scan: `<g fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 9V5.5A1.5 1.5 0 0 1 5.5 4H9M15 4h5v5M20 15v3.5a1.5 1.5 0 0 1-1.5 1.5H15M9 20H5.5A1.5 1.5 0 0 1 4 18.5V15"/></g><rect x="8" y="8" width="8" height="8" rx="1.5" fill="currentColor"/>`,
    clock: `<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3.5 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`,
    trophy: `<path fill="currentColor" d="M7 3h10v2h3v2.5a4.5 4.5 0 0 1-4.1 4.5A5 5 0 0 1 13 14.8V18h3v3H8v-3h3v-3.2A5 5 0 0 1 8.1 12 4.5 4.5 0 0 1 4 7.5V5h3z"/>`,
    drop: `<path fill="currentColor" d="M12 2.5s6.5 7.2 6.5 11.5a6.5 6.5 0 0 1-13 0C5.5 9.7 12 2.5 12 2.5z"/>`,
    mappin: `<path fill="currentColor" d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/><circle cx="12" cy="9" r="2.6" fill="#0B1A11"/>`,
  };
  const icon = (name, cls = "", extra = "") => `<svg class="ico ${cls}" viewBox="0 0 24 24" ${extra}>${ICON[name]}</svg>`;

  window.ART = { LEAF_PATH, BODY, leaf, bottle, CLASSES, icon, ICON, nid };
})();
