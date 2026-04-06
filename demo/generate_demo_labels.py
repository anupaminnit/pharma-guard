"""
Generate realistic pharmaceutical carton mock labels for demo purposes.
Uses Pillow (already in requirements.txt) — no extra dependencies needed.

Run from repo root:
    python demo/generate_demo_labels.py

Outputs:
    demo/sample_labels/ibuprofen_french_NONCOMPLIANT.png   (800x1200)
    demo/sample_labels/ibuprofen_japanese_NONCOMPLIANT.png (800x1200)

Intentional compliance issues are embedded so the AI agents can detect them.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys

OUTPUT_DIR = Path(__file__).parent / "sample_labels"
OUTPUT_DIR.mkdir(exist_ok=True)

W, H = 800, 1200

# ── Colour palette ──────────────────────────────────────────────────────────
NAVY      = (10,  22,  60)
DARK_BLUE = (18,  40,  98)
MID_BLUE  = (28,  60, 140)
WHITE     = (255, 255, 255)
YELLOW    = (255, 210,   0)
RED       = (220,  40,  40)
LIGHT     = (200, 215, 240)
GREY      = (140, 155, 175)
GREEN     = ( 30, 160,  80)


def _font(size: int, bold: bool = False):
    """Return a PIL font, falling back to the built-in bitmap font if needed."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _text(draw, xy, text, font, fill=WHITE, anchor="la"):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _box(draw, xy, fill, outline=None, width=2, radius=6):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _divider(draw, y, color=MID_BLUE, margin=40):
    draw.line([(margin, y), (W - margin, y)], fill=color, width=1)


# ══════════════════════════════════════════════════════════════════════════════
# FRENCH LABEL  (non-compliant: wrong dosage cap + missing renal warning)
# ══════════════════════════════════════════════════════════════════════════════
def generate_french():
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    # ── Header band ──────────────────────────────────────────────────────────
    _box(draw, [(0, 0), (W, 130)], DARK_BLUE)
    _text(draw, (W // 2, 30), "IBUPROFÈNE", _font(42, bold=True), YELLOW, anchor="mt")
    _text(draw, (W // 2, 82), "400 mg  Comprimés pelliculés", _font(18), LIGHT, anchor="mt")
    _text(draw, (W // 2, 110), "Médicament — Autorisation de mise sur le marché n° FR/H/0123/001", _font(11), GREY, anchor="mt")

    # ── Regulatory strip ─────────────────────────────────────────────────────
    _box(draw, [(0, 130), (W, 158)], MID_BLUE)
    _text(draw, (40, 144), "Laboratoires Viatris France · Paris, France", _font(12), LIGHT, anchor="lm")
    _text(draw, (W - 40, 144), "Liste I — Sur ordonnance", _font(12), YELLOW, anchor="rm")

    y = 178

    # ── Composition ──────────────────────────────────────────────────────────
    _text(draw, (40, y), "COMPOSITION", _font(13, bold=True), YELLOW)
    y += 26
    _text(draw, (40, y), "Principe actif : Ibuprofène 400 mg par comprimé", _font(14), WHITE)
    y += 22
    _text(draw, (40, y), "Excipients : Cellulose microcristalline, Croscarmellose sodique,", _font(12), LIGHT)
    y += 18
    _text(draw, (40, y), "Stéarate de magnésium, Hypromellose, Dioxyde de titane (E171),", _font(12), LIGHT)
    y += 18
    _text(draw, (40, y), "Macrogol 400, Laque aluminique d'indigotine (E132).", _font(12), LIGHT)
    y += 28
    _divider(draw, y)
    y += 18

    # ── Indications ──────────────────────────────────────────────────────────
    _text(draw, (40, y), "INDICATIONS THÉRAPEUTIQUES", _font(13, bold=True), YELLOW)
    y += 26
    for line in [
        "Traitement symptomatique des douleurs légères à modérées :",
        "maux de tête, douleurs dentaires, dysménorrhées, douleurs",
        "lombaires. Traitement de la fièvre. Arthrite rhumatoïde.",
    ]:
        _text(draw, (40, y), line, _font(13), WHITE)
        y += 20
    y += 10
    _divider(draw, y)
    y += 18

    # ── Posologie ─────────────────────────────────────────────────────────────
    _text(draw, (40, y), "POSOLOGIE ET MODE D'ADMINISTRATION", _font(13, bold=True), YELLOW)
    y += 26
    _text(draw, (40, y), "Adultes et enfants de 12 ans et plus :", _font(13, bold=True), WHITE)
    y += 22
    _text(draw, (40, y), "1 à 2 comprimés, jusqu'à 3 fois par jour.", _font(13), WHITE)
    y += 20

    # ⚠ INTENTIONAL ISSUE #1 — wrong max dose (1600 mg, correct is 2400 mg)
    _box(draw, [(40, y), (W - 40, y + 36)], (80, 20, 20), RED, width=2)
    _text(draw, (W // 2, y + 18),
          "Ne pas dépasser 4 comprimés (1600 mg) en 24 heures.",
          _font(13, bold=True), WHITE, anchor="mm")
    y += 48

    _text(draw, (40, y), "Avaler les comprimés avec un grand verre d'eau de préférence", _font(12), LIGHT)
    y += 18
    _text(draw, (40, y), "pendant ou après les repas.", _font(12), LIGHT)
    y += 28
    _divider(draw, y)
    y += 18

    # ── Contre-indications ────────────────────────────────────────────────────
    _text(draw, (40, y), "CONTRE-INDICATIONS", _font(13, bold=True), YELLOW)
    y += 26
    for line in [
        "• Hypersensibilité à l'ibuprofène, à l'aspirine ou aux AINS.",
        "• Ulcère gastroduodénal évolutif, antécédents hémorragiques.",
        "• Insuffisance hépatique sévère ou insuffisance cardiaque sévère.",
        "• Troisième trimestre de la grossesse.",
    ]:
        _text(draw, (40, y), line, _font(12), WHITE)
        y += 20

    # ⚠ INTENTIONAL ISSUE #2 — renal impairment warning MISSING entirely
    # (English master has: "Not recommended in patients with renal impairment CrCl <30 mL/min")
    y += 10
    _divider(draw, y)
    y += 18

    # ── Mises en garde ────────────────────────────────────────────────────────
    _text(draw, (40, y), "MISES EN GARDE ET PRÉCAUTIONS D'EMPLOI", _font(13, bold=True), YELLOW)
    y += 26
    for line in [
        "• Risque accru d'événements thrombotiques cardiovasculaires graves.",
        "• Contient du lactose — consulter un médecin en cas d'intolérance.",
        "• Ne pas utiliser en association avec d'autres AINS.",
        "• Éviter l'utilisation prolongée sans avis médical.",
    ]:
        _text(draw, (40, y), line, _font(12), WHITE)
        y += 20
    y += 10
    _divider(draw, y)
    y += 18

    # ── Conservation ──────────────────────────────────────────────────────────
    _text(draw, (40, y), "CONSERVATION", _font(13, bold=True), YELLOW)
    y += 26
    _text(draw, (40, y), "À conserver à une température inférieure à 25°C.", _font(13), WHITE)
    y += 20
    _text(draw, (40, y), "Tenir hors de la portée et de la vue des enfants.", _font(13), WHITE)
    y += 20
    _text(draw, (40, y), "Conserver dans l'emballage d'origine, à l'abri de l'humidité.", _font(12), LIGHT)
    y += 28
    _divider(draw, y)
    y += 14

    # ── Footer ────────────────────────────────────────────────────────────────
    _box(draw, [(0, H - 90), (W, H)], DARK_BLUE)
    _text(draw, (40, H - 68), "Lot / N° de série : voir fond de boîte", _font(11), GREY)
    _text(draw, (40, H - 50), "Date de péremption : voir fond de boîte", _font(11), GREY)
    _text(draw, (40, H - 32), "20 comprimés pelliculés  |  FR-IBU400-2024-001", _font(11), GREY)

    # Barcode placeholder
    for i in range(55):
        bw = 2 if i % 5 != 0 else 4
        bx = W - 180 + i * 3
        draw.rectangle([(bx, H - 78), (bx + bw - 1, H - 14)], fill=WHITE if i % 2 == 0 else NAVY)
    _text(draw, (W - 90, H - 10), "3400935676551", _font(9), GREY, anchor="mb")

    out = OUTPUT_DIR / "ibuprofen_french_NONCOMPLIANT.png"
    img.save(out, "PNG", dpi=(150, 150))
    print(f"✓ Saved {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# JAPANESE LABEL  (non-compliant: INN missing, storage temp missing, no PMDA no.)
# ══════════════════════════════════════════════════════════════════════════════
def generate_japanese():
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    # Try to load a font that can render CJK — fall back gracefully
    def _jp_font(size, bold=False):
        candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Arial Unicode.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
        return _font(size, bold)

    jf_lg = _jp_font(36, bold=True)
    jf_md = _jp_font(16)
    jf_sm = _jp_font(13)
    jf_xs = _jp_font(11)

    # ── Header band ──────────────────────────────────────────────────────────
    _box(draw, [(0, 0), (W, 140)], DARK_BLUE)
    _text(draw, (W // 2, 28), "イブプロフェン錠 400mg", jf_lg, YELLOW, anchor="mt")
    _text(draw, (W // 2, 84), "フィルムコーティング錠", jf_md, LIGHT, anchor="mt")

    # ⚠ INTENTIONAL ISSUE #1 — INN (ibuprofen) not stated in Roman script
    # PMDA requires both Japanese name AND the INN in parentheses
    _text(draw, (W // 2, 112), "【一般用医薬品】  第2類医薬品", jf_sm, GREY, anchor="mt")

    # ── Regulatory band ──────────────────────────────────────────────────────
    _box(draw, [(0, 140), (W, 166)], MID_BLUE)
    _text(draw, (40, 153), "製造販売元：ヴィアトリス製薬株式会社　東京都港区", jf_xs, LIGHT, anchor="lm")
    # ⚠ INTENTIONAL ISSUE #2 — PMDA approval number absent (should be: 承認番号 XXXXXX)

    y = 186

    # ── 成分・分量 ─────────────────────────────────────────────────────────
    _text(draw, (40, y), "【成分・分量】", jf_md, YELLOW)
    y += 28
    _text(draw, (40, y), "1錠中：イブプロフェン 400mg", jf_md, WHITE)
    y += 22
    _text(draw, (40, y), "添加物：結晶セルロース、クロスカルメロースナトリウム、ステアリン酸マグネシウム、", jf_sm, LIGHT)
    y += 18
    _text(draw, (40, y), "ヒプロメロース、酸化チタン、マクロゴール400、インジゴカルミンアルミニウムレーキ", jf_sm, LIGHT)
    y += 26
    _divider(draw, y)
    y += 18

    # ── 効能・効果 ─────────────────────────────────────────────────────────
    _text(draw, (40, y), "【効能・効果】", jf_md, YELLOW)
    y += 28
    for line in [
        "頭痛、歯痛、生理痛、腰痛、関節痛、筋肉痛、神経痛、",
        "肩こり痛の鎮痛。悪寒・発熱時の解熱。",
        "慢性関節リウマチ・変形性関節症の消炎・鎮痛。",
    ]:
        _text(draw, (40, y), line, jf_sm, WHITE)
        y += 20
    y += 8
    _divider(draw, y)
    y += 18

    # ── 用法・用量 ─────────────────────────────────────────────────────────
    _text(draw, (40, y), "【用法・用量】", jf_md, YELLOW)
    y += 28
    _text(draw, (40, y), "成人（15歳以上）：1回1〜2錠、1日3回を限度とする。", jf_md, WHITE)
    y += 22
    _box(draw, [(40, y), (W - 40, y + 34)], (80, 20, 20), RED, width=2)
    _text(draw, (W // 2, y + 17), "1日最大6錠（2400mg）を超えないこと。", jf_md, WHITE, anchor="mm")
    y += 46
    _text(draw, (40, y), "食後または食事中に、十分な量の水またはぬるま湯で服用すること。", jf_sm, LIGHT)
    y += 26
    _divider(draw, y)
    y += 18

    # ── 禁忌 ──────────────────────────────────────────────────────────────
    _text(draw, (40, y), "【禁忌（次の人は使用しないこと）】", jf_md, YELLOW)
    y += 28
    for line in [
        "・本剤またはアスピリン・他のNSAIDsに過敏症の既往歴がある人",
        "・消化性潰瘍のある人",
        "・重篤な肝機能障害または心不全がある人",
        "・妊娠後期（妊娠28週以降）の妊婦",
        "・15歳未満の小児",
    ]:
        _text(draw, (40, y), line, jf_sm, WHITE)
        y += 20
    y += 8
    _divider(draw, y)
    y += 18

    # ── 使用上の注意 ───────────────────────────────────────────────────────
    _text(draw, (40, y), "【使用上の注意】", jf_md, YELLOW)
    y += 28
    for line in [
        "・重大なリスク：心血管血栓イベントのリスクが増加する可能性。",
        "・腎機能が低下している患者では慎重に投与すること。",   # present but vague — missing CrCl threshold
        "・ラクトース含有：乳糖不耐症の患者は医師に相談すること。",
        "・授乳中の使用は医師または薬剤師に相談すること。",
    ]:
        _text(draw, (40, y), line, jf_sm, WHITE)
        y += 20
    y += 8
    _divider(draw, y)
    y += 18

    # ── 保管および取扱い ────────────────────────────────────────────────────
    _text(draw, (40, y), "【保管および取扱い上の注意】", jf_md, YELLOW)
    y += 28
    # ⚠ INTENTIONAL ISSUE #3 — storage temperature omitted (master: "Store below 25°C")
    _text(draw, (40, y), "・小児の手の届かない場所に保管すること。", jf_sm, WHITE)
    y += 20
    _text(draw, (40, y), "・湿気を避け、開封後は元の容器に保管すること。", jf_sm, WHITE)
    y += 20
    _text(draw, (40, y), "・使用期限を過ぎた製品は使用しないこと。", jf_sm, WHITE)
    y += 28
    _divider(draw, y)
    y += 14

    # ── Footer ────────────────────────────────────────────────────────────
    _box(draw, [(0, H - 90), (W, H)], DARK_BLUE)
    _text(draw, (40, H - 68), "ロット番号：箱底面参照", jf_xs, GREY)
    _text(draw, (40, H - 50), "使用期限：箱底面参照", jf_xs, GREY)
    _text(draw, (40, H - 32), "20錠入り　｜　JP-IBU400-2024-001", jf_xs, GREY)

    for i in range(55):
        bw = 2 if i % 5 != 0 else 4
        bx = W - 180 + i * 3
        draw.rectangle([(bx, H - 78), (bx + bw - 1, H - 14)], fill=WHITE if i % 2 == 0 else NAVY)
    _text(draw, (W - 90, H - 10), "4987123456789", _font(9), GREY, anchor="mb")

    out = OUTPUT_DIR / "ibuprofen_japanese_NONCOMPLIANT.png"
    img.save(out, "PNG", dpi=(150, 150))
    print(f"✓ Saved {out}")
    return out


if __name__ == "__main__":
    print("Generating demo pharmaceutical carton labels...")
    fr = generate_french()
    ja = generate_japanese()
    print()
    print("Demo files ready:")
    print(f"  French  → {fr}")
    print(f"  Japanese → {ja}")
    print()
    print("Intentional compliance issues embedded:")
    print("  French:   (1) dosage cap 1600mg vs master 2400mg  (2) renal impairment warning missing")
    print("  Japanese: (1) INN not in Roman script  (2) PMDA approval number absent  (3) storage temp missing")
