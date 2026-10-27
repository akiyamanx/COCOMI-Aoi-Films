# 『24時間ログ』 spec / timeline v2  (stage 360x640 logical, letterboxed with ambient sky)

## Story in one line
白い円盤は世界を壊しに来たように見える。でも本当は「ふつうの一日」を**集めに**来ていた。
24個の2秒は、新しい世界の最初の夢の材料になる。2周目は、その新しい世界の「ちがう、ふつうの一日」。

## Clock / passes
Single clock T (s). Layout (core.js `pstart/plen/passAt`):
- pass 1 (p0) = A, DA = 94.5 s, no card.
- pass 2 (p1) = title card (CARDLEN 3.6 s) + B body (DB ≈ 79.9 s). ≈ 83.5 s.
- pass 3 (p2) = title card (「3周目 / はじまりの一日」) + A again (98.1 s).
- then B, A, … (odd = B, even = A).
B draws with the same drawing code through a piecewise time warp (`taOf/tlOf`): the 8 clips stay 1:1 (2.6 s each, gaps trimmed to .2 s), ta 39-52 ×1.6, 52-74 ×1.15, 74-81 ×1.0, 81-94.5 ×1.15.
`?t=` = global T. `?pass=N&t=x` = body time x of pass N.

## Pass A (T 0-94.5) — "こわしに来たんじゃなかった"
| t (s) | visuals | caption / text | sound |
|---|---|---|---|
| 0-0.25 | black, glitch | – | hum |
| 0.25-1.4 | white disc blooms, rings | – | sub boom |
| 0.9-4.7 | disc text types on disc | 「24時間後に、世界を上書き保存します。」 + (2.9-5.0) hidden whisper **「いちばん ふつうの一日を、ください。」** | tick, soft rising "?" tone at 3.0 |
| 4.2-6.2 | disc rises; walkers, windows | 4.6-8.2 「みんな、いつも通りに過ごすことにした。」 | drone |
| 8.2-11 | HUD, viewfinder demo | 「1時間ごとに、2秒だけ録画する。」 | – |
| 11-39 | 8 clips ×3.5 s (h1-6,11,12); a tiny lantern 🏮 sits in every clip | 寝ぐせ… / **15.0-18.1 「どうして、ふつうの一日なんだろう。」(question planted)** / 缶コーヒー / いつも通り / 特別なことは、なにもしない / 笑って、くだらない話を | beep per hour |
| 39.5-44 | disc cracks, shake, magenta slit, warm beam | 「そのとき、円盤にひびが入った。」 | crackle, thump |
| 44-48 | 12 clips fly into the slit | **「円盤は、こわしに来たんじゃなかった。」** | warm chord |
| 46.4+ | **seed globe 「新しい世界のたね」** forms in the disc; grows & gets a gold light per arrived clip, pulse on arrival | 48.1-52.8 **「新しい世界の材料に、ふつうの一日を集めていたんだ。」** | chirps → bells |
| 52-74 | hours 13-24, live clips (自転車/二人/窓の灯り), lights rise | 53.2-57.8 「24個の2秒が、空へのぼる。」 **58.2-62.6 「人が録った2秒が、世界の最初の夢になる。」 62.9-66.6 「ふつうの毎日でも、ちゃんと材料なんだ。」** 67-73 缶コーヒー… | bell melody |
| 73.6-76.3 | bloom (≤.55) ; seed fades into it | – | swell |
| 76.3-80.5 | disc becomes sun | – | – |
| 77.5-90 | **new world blooms: sprouts/flowers on roofs, grass on street** | – | – |
| 81-88.2 | dawn | 「世界は、ふつうの一日を覚えていた。」 | chord |
| 85.5-91 | credit 制作：葵（COCOMI Family）; **world lantern** rises to (66,330) | – | – |
| 90.2-91.6 | HOUR rolls 24→00 | – | ticks |
| 93.2-94.5 | fade to black | – | – |

## Title card (3.6 s, p>0)
ambient sky continues (t<0), fade from black 0-.7 s, text alpha .35-1 in, out at 2.9-3.55. Texts at logical y 196-450 (clear of top-right buttons, capBox registered).
- B: pill 「2周目」, 「新しい世界」, "NEW WORLD  00:00", 「こんどは、ちょっとちがうよ。」, big lantern. Soft chime: D-major music-box arpeggio.
- A (p≥2): 「3周目」「はじまりの一日」 "DAY ONE  00:00" 「もう一度、あの日から。」 Chime: C-major.

## Pass B (2周目, "this time it is different")
| differences from A |
|---|
| Sky: dawn peach/lilac (SKYB) instead of deep indigo; stars ×.3; city lighter, windows already warm; warm gold halo, no neon, **no crack, no shake, no glitch/VHS pink**, scanlines/vignette lighter, flights glow gold, cards have warm shadow & no REC-pink overlay, no viewfinder demo. |
| Disc glows gently (gold ring + breathing halo), tiny frames glimmer inside. Disc text 「24時間後に、世界を、はじめから。」 (warm orange highlight). |
| 8 hourly clips = **different ordinary scenes**: 土から芽が出た(h1) / 傘を半分こ(h2) / 夜の窓の灯り(h3) / 星を見上げる子(h4) / 猫のあくび(h5) / 雨上がりの水たまり(h6) / 席をゆずる(h11) / 手を振る(h12); live: 朝のパン屋 / ブランコ / 洗濯物の風. Same drawing system. |
| Lantern companion: big in every B clip; hovers next to the disc (ta 3-40), flies to the seed (40-60, 「あの灯りも、新しい世界へ。」), reappears in the new world (ta 79-93). |
| Captions (gold highlighter, no chromatic offsets): こんどの円盤は、ちょっとやさしい光。/ 前の世界の小さな灯りも、いっしょに来たよ。/ まず芽が出て、傘を半分こ。/ 夜の窓に灯りがついて、星を見上げる。/ 猫があくびして、水たまりをぴょん。/ 席をゆずって、手を振る。/ あつめた2秒が、光になって空へ。/ どんなにふつうでも、ちゃんと世界の材料。/ あの灯りも、新しい世界へ。/ ふつうの一日が、新しい世界のはじまり。/ ひとつひとつが、世界の灯りになる。/ **最後: 「世界は、ふつうの一日から、はじまった。」** + credit |
| Sound: D-major pentatonic music-box/marimba melody, soft pad chord at dawn (D major), no square beeps, D drone. |

## Quality bars
CSP meta (`default-src 'none'`…), no network, `prefers-reduced-motion` (reduce → no shake/glitch, calmer), WebAudio only (silent until a gate button), aria-live caption text, `?t=`/`?pass=` jump, `window.__seek/__state` test hooks.
