import random
import time
import streamlit as st

st.set_page_config(page_title="自宅ネットワークトラブル解決教材", layout="wide")

# =========================================================
# 固定データ（4つの障害シナリオ）
# =========================================================
FAULT_SCENARIOS = {
    "①": {
        "cause": "LANケーブルの接触不良・断線（HUB〜デスクトップPC間）",
        "results": {"a": "〇", "b": "〇", "c": "×", "d": "〇"},
        "highlight": {"type": "edge", "edge": ("HUB", "Desktop")},
        "hint": "デスクトップPC以外はすべて〇です。HUBやルーター自体は生きているのに、"
                "デスクトップPCだけに届かない…影響範囲が最も狭いのはどこでしょう？",
    },
    "②": {
        "cause": "HUBの障害（特定ポートの故障）",
        "results": {"a": "×", "b": "〇", "c": "×", "d": "×"},
        "highlight": {"type": "node", "node": "HUB"},
        "hint": "無線AP（b）だけは〇です。有線でHUBに直接ぶら下がる機器（ルーター側・デスクトップPC・プリンタ）"
                "だけが×になっているのがポイントです。",
    },
    "③": {
        "cause": "無線LANアクセスポイントの障害（無線AP本体の故障）",
        "results": {"a": "×", "b": "×", "c": "×", "d": "×"},
        "highlight": {"type": "node", "node": "AP"},
        "hint": "全部×です。ノートPC自体が無線でしかネットワークに出られないことを考えると、"
                "ノートPCの出口そのものが怪しいです。",
    },
    "④": {
        "cause": "ルーターの障害（ルーター本体の故障）",
        "results": {"a": "×", "b": "〇", "c": "〇", "d": "〇"},
        "highlight": {"type": "node", "node": "Router"},
        "hint": "ルーター（a）以外はすべて〇です。LAN内部の通信（HUB配下）は生きているのに、"
                "ルーターへだけ届かない、という点に注目しましょう。",
    },
}

TARGET_NAMES = {
    "a": "ルーター",
    "b": "無線LANアクセスポイント",
    "c": "デスクトップPC",
    "d": "プリンタ",
}
TARGET_IPS = {
    "a": "192.168.1.1",
    "b": "192.168.1.2",
    "c": "192.168.1.10",
    "d": "192.168.1.20",
}
KEY_TO_NODE = {"a": "Router", "b": "AP", "c": "Desktop", "d": "Printer"}

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
        "current_fault": None,        # ランダムに決まる正解（①〜④）
        "checked": {k: False for k in TARGET_NAMES},
        "ping_logs": {},              # key -> ターミナル風ログ文字列
        "submitted": False,
        "selected_answer": "-- 選択してください --",
        "wrong_attempts": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def reset_all():
    st.session_state.started = False
    st.session_state.trouble = False
    st.session_state.checking = False
    st.session_state.current_fault = None
    st.session_state.checked = {k: False for k in TARGET_NAMES}
    st.session_state.ping_logs = {}
    st.session_state.submitted = False
    st.session_state.selected_answer = "-- 選択してください --"
    st.session_state.wrong_attempts = 0

def make_ping_log(name, ip, success):
    lines = [f"$ ping {ip}", f"PING {ip} ({ip}): 56 data bytes"]
    if success:
        for seq in range(3):
            lines.append(f"64 bytes from {ip}: icmp_seq={seq} ttl=64 time={0.4 + seq * 0.3:.1f} ms")
        lines.append(f"--- {name} ping statistics ---")
        lines.append("3 packets transmitted, 3 packets received, 0.0% packet loss")
    else:
        for seq in range(3):
            lines.append(f"Request timeout for icmp_seq {seq}")
        lines.append(f"--- {name} ping statistics ---")
        lines.append("3 packets transmitted, 0 packets received, 100.0% packet loss")
    return "\n".join(lines)

# =========================================================
# ネットワーク図（SVG）
# =========================================================
def build_network_svg(highlight=None, status=None):
    """
    highlight: {'type':'edge','edge':(a,b)} または {'type':'node','node':key} または None
    status: {node_key: 'ok' または 'ng'}  疎通確認済みの機器にバッジを表示
    """
    status = status or {}
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
        ("ISP", "Router", "solid"),
        ("Router", "HUB", "solid"),
        ("HUB", "AP", "solid"),
        ("HUB", "Desktop", "solid"),
        ("HUB", "Printer", "solid"),
        ("AP", "NotePC", "dashed"),
    ]

    fault_edge = highlight["edge"] if highlight and highlight["type"] == "edge" else None
    fault_node = highlight["node"] if highlight and highlight["type"] == "node" else None

    svg_parts = [
        '<svg viewBox="0 0 500 430" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;max-width:600px;height:auto;font-family:sans-serif;">'
    ]

    for start, end, style in edges:
        n1, n2 = nodes[start], nodes[end]
        x1, y1 = n1["x"], n1["y"] + n1["h"] / 2
        x2, y2 = n2["x"], n2["y"] - n2["h"] / 2
        dash = ' stroke-dasharray="6,5"' if style == "dashed" else ""
        is_fault = fault_edge is not None and set(fault_edge) == {start, end}
        if is_fault:
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
        is_fault_node = (key == fault_node)
        stroke = "#d9333f" if is_fault_node else "#555555"
        stroke_width = 4 if is_fault_node else 1.5
        svg_parts.append(
            f'<rect x="{x - w/2}" y="{y - h/2}" width="{w}" height="{h}" rx="8" ry="8" '
            f'fill="{n["color"]}" stroke="{stroke}" stroke-width="{stroke_width}" />'
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
        if is_fault_node:
            svg_parts.append(
                f'<text x="{x}" y="{y + h/2 + 16}" text-anchor="middle" '
                f'fill="#d9333f" font-size="13" font-weight="bold">故障！</text>'
            )

        # 疎通確認済みバッジ（右上に表示）
        if key in status:
            bx, by = x + w / 2 - 4, y - h / 2 - 4
            ok = status[key] == "ok"
            badge_color = "#2e9e44" if ok else "#d9333f"
            mark = "\u2713" if ok else "\u2715"
            svg_parts.append(
                f'<circle cx="{bx}" cy="{by}" r="11" fill="{badge_color}" '
                f'stroke="white" stroke-width="2" />'
            )
            svg_parts.append(
                f'<text x="{bx}" y="{by + 4}" text-anchor="middle" '
                f'font-size="13" font-weight="bold" fill="white">{mark}</text>'
            )

    svg_parts.append("</svg>")
    return "".join(svg_parts)

# =========================================================
# 画面構成
# =========================================================
st.title("🏠 自宅ネットワークトラブル解決教材")
st.caption("実際に疎通確認コマンドを打つ感覚で、トラブルの原因を突き止めよう")

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
            "発生したトラブルの原因を疎通確認によって特定していきます。"
            "実際のping結果を見ながら、原因を推理してみましょう。")
    if st.button("▶ スタート", type="primary"):
        st.session_state.started = True
        st.rerun()

# ---- ステップ2：構成図の表示 ----
if st.session_state.started:
    st.subheader("① ネットワーク構成")

    show_answer = (st.session_state.submitted and
                    st.session_state.selected_answer == st.session_state.current_fault)
    highlight = None
    if show_answer and st.session_state.current_fault:
        highlight = FAULT_SCENARIOS[st.session_state.current_fault]["highlight"]

    status = {}
    if st.session_state.current_fault:
        current_results = FAULT_SCENARIOS[st.session_state.current_fault]["results"]
        for key, node_key in KEY_TO_NODE.items():
            if st.session_state.checked.get(key):
                status[node_key] = "ok" if current_results[key] == "〇" else "ng"

    diagram_slot = st.empty()
    diagram_slot.markdown(build_network_svg(highlight, status), unsafe_allow_html=True)

    if not st.session_state.trouble:
        st.write("上図が現在の自宅ネットワーク構成です。機器をよく見ておきましょう。")
        if st.button("⚠ トラブル発生", type="primary"):
            st.session_state.trouble = True
            st.session_state.current_fault = random.choice(list(FAULT_SCENARIOS.keys()))
            st.rerun()

# ---- ステップ3：トラブル発生メッセージ ----
if st.session_state.trouble:
    st.subheader("② トラブル発生")
    st.error("ネットワークに障害が発生しました。疎通確認を行い、トラブルが起きた機器を特定してください。")

    if not st.session_state.checking:
        st.write("ノートPCから疎通確認を行います。")
        if st.button("疎通確認を開始する", type="primary"):
            st.session_state.checking = True
            st.rerun()

# ---- ステップ4：疎通確認（クリックで実際のping風シミュレーション） ----
if st.session_state.checking:
    st.subheader("③ 疎通確認コンソール")
    st.write("ノートPCのターミナルから、確認したい機器へ ping を実行してみましょう。"
             "クリックすると実際にコマンドを打ったような結果が返ってきます。")

    current_results = FAULT_SCENARIOS[st.session_state.current_fault]["results"]

    cols = st.columns(4)
    for i, key in enumerate(TARGET_NAMES):
        with cols[i]:
            already = st.session_state.checked[key]
            label = f"{key}. {TARGET_NAMES[key]}" + (" ✅" if already else "")
            if st.button(f"📡 {label} へ ping", key=f"btn_{key}", disabled=already):
                name = TARGET_NAMES[key]
                ip = TARGET_IPS[key]
                success = current_results[key] == "〇"
                with st.spinner(f"ノートPC → {name}（{ip}）へ疎通確認中…"):
                    time.sleep(0.9)
                st.session_state.ping_logs[key] = make_ping_log(name, ip, success)
                st.session_state.checked[key] = True
                st.toast(
                    f"{name} への疎通：{'成功 〇' if success else '失敗 ×'}",
                    icon="✅" if success else "🚫",
                )
                st.rerun()

    st.write("")
    if st.session_state.ping_logs:
        st.markdown("**pingコンソール出力**")
        for key in TARGET_NAMES:
            if key in st.session_state.ping_logs:
                with st.expander(f"{key}. {TARGET_NAMES[key]} への ping 結果", expanded=True):
                    st.code(st.session_state.ping_logs[key], language="text")

    all_checked = all(st.session_state.checked.values())
    if not all_checked:
        remaining = [f"{k}.{TARGET_NAMES[k]}" for k in TARGET_NAMES if not st.session_state.checked[k]]
        st.caption(f"未確認：{' / '.join(remaining)}")

    # ---- ステップ5：原因の推理 ----
    if all_checked:
        st.subheader("④ トラブルの原因を推理しよう")
        st.write("疎通確認の結果（図の✓✕バッジとping結果）から、"
                 "想定される障害①〜④のうち、最も可能性が高いものを1つ選んでください。")

        if st.session_state.wrong_attempts >= 1 and not st.session_state.submitted:
            with st.expander("💡 ヒントを見る（考え方のポイント）"):
                st.write(FAULT_SCENARIOS[st.session_state.current_fault]["hint"])

        options = ["-- 選択してください --"] + [
            f"{k} {v['cause']}" for k, v in FAULT_SCENARIOS.items()
        ]
        choice = st.selectbox("想定される障害", options, key="answer_select")
        choice_key = choice.split(" ")[0] if choice != "-- 選択してください --" else None

        if st.button("この原因で回答する", type="primary", disabled=(choice_key is None)):
            st.session_state.submitted = True
            st.session_state.selected_answer = choice_key
            if choice_key != st.session_state.current_fault:
                st.session_state.wrong_attempts += 1
            st.rerun()

        if st.session_state.submitted:
            correct = st.session_state.current_fault
            if st.session_state.selected_answer == correct:
                st.success("✅ 正解です！")
                st.balloons()
                attempts_msg = (
                    "一発で正解、お見事です！" if st.session_state.wrong_attempts == 0
                    else f"（{st.session_state.wrong_attempts}回の再挑戦の末の正解でした。お疲れさまでした！）"
                )
                st.markdown(
                    f"**解説**：正解は「{FAULT_SCENARIOS[correct]['cause']}」でした。{attempts_msg}\n\n"
                    "上のネットワーク構成図で、故障箇所が赤く表示されています。"
                    "疎通確認の結果（〇/×のパターン）から、どの機器・区間が影響範囲に含まれているかを"
                    "たどることで、故障箇所を絞り込むことができます。"
                )
            else:
                st.error("❌ 残念、正解ではありません。")
                st.markdown(
                    "**考え方のヒント**：疎通確認結果で「×」になっている機器と「〇」になっている機器を見比べ、"
                    "どの機器が故障・断線すると、ちょうどこの〇×のパターンになるかを、"
                    "ネットワーク構成図をたどりながら考えてみましょう。"
                    "たとえば、ある機器から先の区間だけがすべて×になっている場合、"
                    "その手前の機器や区間に原因がある可能性が高いです。"
                )
                if st.session_state.wrong_attempts >= 2:
                    st.info(f"💡 ヒント：{FAULT_SCENARIOS[correct]['hint']}")
                if st.button("もう一度選び直す"):
                    st.session_state.submitted = False
                    st.session_state.selected_answer = "-- 選択してください --"
                    st.rerun()