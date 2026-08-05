import streamlit as st

st.set_page_config(page_title="自宅ネットワークトラブル解決教材", layout="wide")

# =========================================================
# 固定データ（今回のシナリオ）
# =========================================================
FAULT_OPTIONS = {
    "①": "LANケーブルの接触不良・断線（ノートPC〜無線AP間、無線AP〜HUB間、またはHUB〜デスクトップPC間）",
    "②": "HUBの障害（特定ポートの故障）",
    "③": "無線LANアクセスポイントの障害（無線AP本体の故障）",
    "④": "ルーターの障害（ルーター本体の故障、または特定ポートの不具合）",
}
CORRECT_ANSWER = "①"

PING_TARGETS = {
    "a": {"name": "ルーター", "result": "〇"},
    "b": {"name": "無線LANアクセスポイント", "result": "〇"},
    "c": {"name": "デスクトップPC", "result": "×"},
    "d": {"name": "プリンタ", "result": "〇"},
}

KNOWLEDGE_MEMO = [
    ("① ISP（インターネットサービスプロバイダ）",
     "自宅のネットワーク（LAN）と巨大なインターネット網を接続する事業者。",
     "回線接続サービスの提供／グローバルIPアドレスの割り当て／DNSやメール等の付加サービス",
     "前提として除外：小規模LAN内のハードウェア障害を対象とするため、今回は影響範囲外（正常とみなす）。"),
    ("② ルーター",
     "異なるネットワーク（家庭内LANとインターネット）の間で、データの経路制御（ルーティング）を行う中継機器。",
     "パケットの経路選択（レイヤー3）／IPアドレスの自動割り当て（DHCP）",
     "上位層・コア機器：ここが故障すると、インターネット接続だけでなくローカル通信やDHCPによるIP配布にも影響が出ることがある。"),
    ("③ HUB",
     "LANケーブルを用いて、同一ネットワーク内の複数の機器同士を接続・中継する機器。",
     "複数ポートでの同時通信の効率化／LEDランプによるリンク状態（通電・通信中）の可視化",
     "有線機器（デスクトップPC、プリンタ、無線APなど）が集まる中心。ポートの故障や電源断が起これば直下の機器が孤立する。"),
    ("④ 無線LANアクセスポイント（Wi-Fi親機）",
     "有線LANのネットワークを、電波を使った無線LAN（Wi-Fi）のネットワークに変換・接続する機器。",
     "有線と無線のブリッジ接続（レイヤー2〜1）／電波による無線端末（ノートPC等）との通信管理",
     "ノートPCなどの無線端末をLANに繋ぐ窓口。ここが故障または電源が落ちると、無線端末全体のネットワークが遮断される。"),
]

# =========================================================
# セッション状態の初期化
# =========================================================
def init_state():
    defaults = {
        "started": False,
        "trouble": False,
        "checking": False,
        "checked": {k: False for k in PING_TARGETS},
        "submitted": False,
        "selected_answer": "-- 選択してください --",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def reset_all():
    st.session_state.started = False
    st.session_state.trouble = False
    st.session_state.checking = False
    st.session_state.checked = {k: False for k in PING_TARGETS}
    st.session_state.submitted = False
    st.session_state.selected_answer = "-- 選択してください --"

# =========================================================
# ネットワーク図（SVG）
# 日本語テキストはブラウザ側のフォントで描画されるため、
# サーバー側に日本語フォントが無くても文字化けしない。
# =========================================================
def build_network_svg(show_fault: bool) -> str:
    nodes = {
        "ISP":     {"x": 250, "y": 30,  "w": 90,  "h": 44, "label": "ISP",              "color": "#e0e0e0"},
        "Router":  {"x": 250, "y": 110, "w": 120, "h": 48, "label": "ルーター",          "color": "#a9d0f5"},
        "HUB":     {"x": 250, "y": 190, "w": 120, "h": 48, "label": "HUB",               "color": "#a9d0f5"},
        "AP":      {"x": 90,  "y": 280, "w": 130, "h": 56, "label": "無線LAN\nアクセスポイント", "color": "#a9d0f5"},
        "Desktop": {"x": 250, "y": 280, "w": 130, "h": 48, "label": "デスクトップPC",     "color": "#f7b6b6"},
        "Printer": {"x": 410, "y": 280, "w": 120, "h": 48, "label": "プリンタ",          "color": "#a9d0f5"},
        "NotePC":  {"x": 90,  "y": 370, "w": 120, "h": 48, "label": "ノートPC",          "color": "#c6f0b6"},
    }
    edges = [
        ("ISP", "Router", "solid", False),
        ("Router", "HUB", "solid", False),
        ("HUB", "AP", "solid", False),
        ("HUB", "Desktop", "solid", True),   # HUB〜デスクトップPC間（今回の障害区間）
        ("HUB", "Printer", "solid", False),
        ("AP", "NotePC", "dashed", False),
    ]

    svg_parts = [
        '<svg viewBox="0 0 500 430" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;max-width:600px;height:auto;font-family:sans-serif;">'
    ]

    for start, end, style, is_fault in edges:
        n1, n2 = nodes[start], nodes[end]
        x1, y1 = n1["x"], n1["y"] + n1["h"] / 2
        x2, y2 = n2["x"], n2["y"] - n2["h"] / 2
        dash = ' stroke-dasharray="6,5"' if style == "dashed" else ""
        if is_fault and show_fault:
            svg_parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="#d9333f" stroke-width="5"{dash} />'
            )
            mx, my = (x1 + x2) / 2 + 12, (y1 + y2) / 2
            svg_parts.append(
                f'<text x="{mx}" y="{my}" fill="#d9333f" font-size="14" '
                f'font-weight="bold">断線！</text>'
            )
        else:
            svg_parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="#888888" stroke-width="2"{dash} />'
            )

    for key, n in nodes.items():
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        svg_parts.append(
            f'<rect x="{x - w/2}" y="{y - h/2}" width="{w}" height="{h}" rx="8" ry="8" '
            f'fill="{n["color"]}" stroke="#555555" stroke-width="1.5" />'
        )
        lines = n["label"].split("\n")
        n_lines = len(lines)
        line_height = 15
        start_y = y - (n_lines - 1) * line_height / 2 + 5
        for i, line in enumerate(lines):
            svg_parts.append(
                f'<text x="{x}" y="{start_y + i * line_height}" text-anchor="middle" '
                f'font-size="13" fill="#222222">{line}</text>'
            )

    svg_parts.append("</svg>")
    return "".join(svg_parts)

# =========================================================
# 画面構成
# =========================================================
st.title("🏠 自宅ネットワークトラブル解決教材")
st.caption("ネットワーク機器の疎通確認を行いながら、トラブルの原因を推理しよう")

with st.sidebar:
    st.header("📘 ナレッジメモ")
    st.write("各機器の役割を確認できます。")
    for name, role, feature, position in KNOWLEDGE_MEMO:
        with st.expander(name):
            st.markdown(f"**主な役割**：{role}")
            st.markdown(f"**具体的な機能・特徴**：{feature}")
            st.markdown(f"**今回の位置づけ**：{position}")
    st.divider()
    if st.button("🔄 最初からやり直す"):
        reset_all()
        st.rerun()

# ---- ステップ1：スタート ----
if not st.session_state.started:
    st.info("このアプリでは、自宅内のネットワーク構成を確認しながら、"
            "発生したトラブルの原因を疎通確認によって特定していきます。")
    if st.button("▶ スタート", type="primary"):
        st.session_state.started = True
        st.rerun()

# ---- ステップ2：構成図の表示 ----
if st.session_state.started:
    st.subheader("① ネットワーク構成")
    show_fault = (st.session_state.submitted and
                  st.session_state.selected_answer == CORRECT_ANSWER)
    st.markdown(build_network_svg(show_fault), unsafe_allow_html=True)

    if not st.session_state.trouble:
        st.write("上図が現在の自宅ネットワーク構成です。")
        if st.button("⚠ トラブル発生", type="primary"):
            st.session_state.trouble = True
            st.rerun()

# ---- ステップ3：トラブル発生メッセージ ----
if st.session_state.trouble:
    st.subheader("② トラブル発生")
    st.error("ノートPCからデスクトップPCへのネットワーク接続ができません")

    if not st.session_state.checking:
        st.write("ノートPCから疎通確認を行います。")
        if st.button("疎通確認を開始する", type="primary"):
            st.session_state.checking = True
            st.rerun()

# ---- ステップ4：疎通確認（クリックで結果表示） ----
if st.session_state.checking:
    st.subheader("③ 疎通確認")
    st.write("下の機器名をクリックすると、ノートPCからその機器への疎通確認結果が表示されます。")

    cols = st.columns(4)
    for i, (key, info) in enumerate(PING_TARGETS.items()):
        with cols[i]:
            if st.button(f"{key}. {info['name']} に疎通確認", key=f"btn_{key}"):
                st.session_state.checked[key] = True
                st.rerun()

    st.write("")
    st.markdown("**疎通確認結果**")
    table_md = "| | 疎通確認先 | 疎通確認結果 |\n|---|---|---|\n"
    for key, info in PING_TARGETS.items():
        result = info["result"] if st.session_state.checked[key] else "未確認"
        table_md += f"| {key} | {info['name']} | {result} |\n"
    st.markdown(table_md)

    all_checked = all(st.session_state.checked.values())

    # ---- ステップ5：原因の推理 ----
    if all_checked:
        st.subheader("④ トラブルの原因を推理しよう")
        st.write("疎通確認の結果から、想定される障害①〜④のうち、"
                 "最も可能性が高いものを1つ選んでください。")

        options = ["-- 選択してください --"] + [
            f"{k} {v}" for k, v in FAULT_OPTIONS.items()
        ]
        choice = st.selectbox("想定される障害", options, key="answer_select")
        choice_key = choice.split(" ")[0] if choice != "-- 選択してください --" else None

        if st.button("この原因で回答する", type="primary", disabled=(choice_key is None)):
            st.session_state.submitted = True
            st.session_state.selected_answer = choice_key
            st.rerun()

        if st.session_state.submitted:
            if st.session_state.selected_answer == CORRECT_ANSWER:
                st.success("✅ 正解です！")
                st.markdown(
                    "**解説**：ルーター（a）・無線LANアクセスポイント（b）・プリンタ（d）への疎通は"
                    "すべて成功しており、ルーターやHUB、無線APといった共有区間の機器は正常に動作しています。"
                    "一方、デスクトップPC（c）だけが疎通できないことから、他の機器に影響を与えない"
                    "**デスクトップPC固有の接続区間（HUB〜デスクトップPC間のLANケーブル）**に問題があると"
                    "推定できます。実際にHUB〜デスクトップPC間のケーブルが接触不良・断線していました。"
                )
            else:
                st.error("❌ 残念、正解ではありません。")
                st.markdown(
                    "**考え方のヒント**：もしHUB・ルーター・無線APのいずれかが故障していれば、"
                    "それらを経由する他の機器（ルーター、無線AP、プリンタ）への疎通にも影響が出るはずです。"
                    "しかし今回はデスクトップPC以外はすべて疎通できています。"
                    "影響が及んでいる範囲が最も狭い原因は何か、もう一度考えてみましょう。"
                )
                if st.button("もう一度選び直す"):
                    st.session_state.submitted = False
                    st.session_state.selected_answer = "-- 選択してください --"
                    st.rerun()