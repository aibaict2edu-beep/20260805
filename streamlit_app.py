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
        "lamp": {"router": "on", "ap": "on", "desktop": "off", "printer": "on"},
        "hint": "デスクトップPC以外はすべて〇です。HUBのランプもデスクトップPC向けのポートだけ消灯しています。"
                "影響範囲が最も狭いのはどこでしょう？",
    },
    "②": {
        "cause": "HUBの障害（特定ポートの故障）",
        "results": {"a": "×", "b": "〇", "c": "×", "d": "×"},
        "highlight": {"type": "node", "node": "HUB"},
        "lamp": {"router": "on", "ap": "on", "desktop": "on", "printer": "on"},
        "hint": "実はHUBのランプは全ポート正常に点灯しています。物理的な接続（リンク）はできていても、"
                "HUB内部での中継処理そのものが壊れていると、ランプは正常なのにpingが通らないことがあります。",
    },
    "③": {
        "cause": "無線LANアクセスポイントの障害（無線AP本体の故障）",
        "results": {"a": "×", "b": "×", "c": "×", "d": "×"},
        "highlight": {"type": "node", "node": "AP"},
        "lamp": {"router": "on", "ap": "off", "desktop": "on", "printer": "on"},
        "hint": "HUB側から見ると、無線APにつながるポートのランプだけが消灯しています。"
                "ノートPCは無線でしかネットワークに出られないことも合わせて考えてみましょう。",
    },
    "④": {
        "cause": "ルーターの障害（ルーター本体の故障）",
        "results": {"a": "×", "b": "〇", "c": "〇", "d": "〇"},
        "highlight": {"type": "node", "node": "Router"},
        "lamp": {"router": "off", "ap": "on", "desktop": "on", "printer": "on"},
        "hint": "ルーターにつながるポートのランプだけが消灯しています。LAN内部（HUB配下）の通信は"
                "生きているのに、ルーターへだけ届かない点に注目しましょう。",
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
NOTEPC_IP = "192.168.1.30"
KEY_TO_NODE = {"a": "Router", "b": "AP", "c": "Desktop", "d": "Printer"}

LAMP_PORTS = {
    "router": {"label": "ルーター向けポート", "key": "a"},
    "ap": {"label": "無線APポート", "key": "b"},
    "desktop": {"label": "デスクトップPCポート", "key": "c"},
    "printer": {"label": "プリンタポート", "key": "d"},
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
        "current_fault": None,        # ランダムに決まる正解（①〜④）
        "checked": {k: False for k in TARGET_NAMES},
        "ping_logs": {},              # key -> ターミナル風ログ文字列
        "lamp_checked": False,
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
    st.session_state.lamp_checked = False
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
# HTMLテーブル生成
# =========================================================
def build_ping_table(current_results, checked):
    rows = []
    for key, name in TARGET_NAMES.items():
        ip = TARGET_IPS[key]
        if checked.get(key):
            success = current_results[key] == "〇"
            if success:
                badge = '<span style="color:#2e9e44;font-weight:bold;">〇 成功</span>'
            else:
                badge = '<span style="color:#d9333f;font-weight:bold;">× 失敗</span>'
        else:
            badge = '<span style="color:#999;">未確認</span>'
        rows.append(
            f'<tr>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{key}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{name}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;font-family:monospace;">{ip}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{badge}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        '<thead><tr style="background:#f5f5f5;">'
        '<th style="padding:6px 10px;text-align:left;">記号</th>'
        '<th style="padding:6px 10px;text-align:left;">機器名</th>'
        '<th style="padding:6px 10px;text-align:left;">IPアドレス</th>'
        '<th style="padding:6px 10px;text-align:left;">Ping結果</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )

def build_lamp_table(lamp_status, lamp_checked):
    rows = []
    for port_key, info in LAMP_PORTS.items():
        if lamp_checked:
            on = lamp_status[port_key] == "on"
            if on:
                badge = '<span style="color:#2e9e44;font-weight:bold;">🟢 点灯（リンクOK）</span>'
            else:
                badge = '<span style="color:#d9333f;font-weight:bold;">🔴 消灯（リンクなし）</span>'
        else:
            badge = '<span style="color:#999;">未確認</span>'
        rows.append(
            f'<tr>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{info["label"]}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{badge}</td>'
            f'</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        '<thead><tr style="background:#f5f5f5;">'
        '<th style="padding:6px 10px;text-align:left;">HUBポート</th>'
        '<th style="padding:6px 10px;text-align:left;">ランプ状態</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    )

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
        "Router":  {"x": 250, "y": 110, "w": 120, "h": 48, "label": "ルーター",          "color": "#a9d0f5", "ip": TARGET_IPS["a"]},
        "HUB":     {"x": 250, "y": 190, "w": 120, "h": 48, "label": "HUB",               "color": "#a9d0f5"},
        "AP":      {"x": 90,  "y": 280, "w": 130, "h": 56, "label": "無線LAN\nアクセスポイント", "color": "#a9d0f5", "ip": TARGET_IPS["b"]},
        "Desktop": {"x": 250, "y": 280, "w": 130, "h": 48, "label": "デスクトップPC",     "color": "#f7b6b6", "ip": TARGET_IPS["c"]},
        "Printer": {"x": 410, "y": 280, "w": 120, "h": 48, "label": "プリンタ",          "color": "#a9d0f5", "ip": TARGET_IPS["d"]},
        "NotePC":  {"x": 90,  "y": 380, "w": 120, "h": 48, "label": "ノートPC",          "color": "#c6f0b6", "ip": NOTEPC_IP},
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
        '<svg viewBox="0 0 500 440" xmlns="http://www.w3.org/2000/svg" '
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
        start_y = y - (n_lines - 1) * line_height / 2 + 3
        for i, line in enumerate(lines):
            svg_parts.append(
                f'<text x="{x}" y="{start_y + i * line_height}" text-anchor="middle" '
                f'font-size="13" fill="#222222">{line}</text>'
            )
        if "ip" in n:
            ip_y = start_y + n_lines * line_height
            svg_parts.append(
                f'<text x="{x}" y="{ip_y}" text-anchor="middle" '
                f'font-size="10.5" fill="#555555">{n["ip"]}</text>'
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
st.markdown(
    """
    <style>
    .sticky-diagram { position: sticky; top: 4rem; }
    .status-card {
        background: #ffffff; border: 1px solid #e6e6e6; border-radius: 10px;
        padding: 14px 16px; margin-top: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-row { display:flex; justify-content:space-between; font-size:14px; padding:4px 0; }
    .status-label { color:#555; }
    .status-value { font-weight:600; }
    div.stButton > button { transition: all 0.15s ease-in-out; }
    div.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 3px 8px rgba(0,0,0,0.12); }
    </style>
    """,
    unsafe_allow_html=True,
)

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

# ---- ステップ1：スタート（構成図の前に表示） ----
if not st.session_state.started:
    st.info("このアプリでは、自宅内のネットワーク構成を確認しながら、"
            "発生したトラブルの原因をpingやHUBのランプ確認によって特定していきます。")
    if st.button("▶ スタート", type="primary"):
        st.session_state.started = True
        st.rerun()
    st.stop()

# ---- ここから：左＝構成図（常時表示・スクロール不要）／右＝操作パネル ----
diagram_col, panel_col = st.columns([0.42, 0.58], gap="large")

with diagram_col:
    st.markdown("### 🗺️ ネットワーク構成図")

    show_answer = (st.session_state.submitted and
                    st.session_state.selected_answer == st.session_state.current_fault)
    highlight = None
    if show_answer and st.session_state.current_fault:
        highlight = FAULT_SCENARIOS[st.session_state.current_fault]["highlight"]

    status = {}
    current_results = None
    current_lamp = None
    if st.session_state.current_fault:
        current_results = FAULT_SCENARIOS[st.session_state.current_fault]["results"]
        current_lamp = FAULT_SCENARIOS[st.session_state.current_fault]["lamp"]
        for key, node_key in KEY_TO_NODE.items():
            if st.session_state.checked.get(key):
                status[node_key] = "ok" if current_results[key] == "〇" else "ng"

    svg = build_network_svg(highlight, status)
    st.markdown(f'<div class="sticky-diagram">{svg}', unsafe_allow_html=True)

    # ---- 進捗ミニダッシュボード（図の直下・常に見える） ----
    checked_count = sum(st.session_state.checked.values())
    trouble_state = "発生中 ⚠️" if st.session_state.trouble else "なし"
    lamp_state = "確認済み 💡" if st.session_state.lamp_checked else "未確認"
    st.markdown(
        f"""
        <div class="status-card">
            <div class="status-row"><span class="status-label">トラブル状態</span>
                <span class="status-value">{trouble_state}</span></div>
            <div class="status-row"><span class="status-label">Ping確認</span>
                <span class="status-value">{checked_count} / 4</span></div>
            <div class="status-row"><span class="status-label">HUBランプ確認</span>
                <span class="status-value">{lamp_state}</span></div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with panel_col:
    # ---- ステップ2：トラブル発生前 ----
    if not st.session_state.trouble:
        st.subheader("① ネットワークは正常です")
        st.write("左の構成図とIPアドレスを確認したら、トラブルを発生させてみましょう。")
        if st.button("⚠ トラブル発生", type="primary", use_container_width=True):
            st.session_state.trouble = True
            st.session_state.current_fault = random.choice(list(FAULT_SCENARIOS.keys()))
            st.rerun()

    # ---- ステップ3：トラブル発生メッセージ ----
    if st.session_state.trouble:
        st.subheader("② トラブル発生")
        st.error("ネットワークに障害が発生しました。ノートPCから疎通確認（ping）を行い、トラブルが起きた機器を特定してください。")

        if not st.session_state.checking:
            st.write("ノートPCから調査を行います。")
            if st.button("調査を開始する", type="primary", use_container_width=True):
                st.session_state.checking = True
                st.rerun()

    # ---- ステップ4：調査（タブでping操作／HUBランプ確認／結果一覧を切り替え） ----
    if st.session_state.checking:
        st.subheader("③ 調査")

        tab_ping, tab_lamp, tab_summary = st.tabs(
            ["📡 ping操作", "💡 HUBランプ確認", "📋 結果一覧"]
        )

        with tab_ping:
            st.caption(f"ノートPC（{NOTEPC_IP}）から各機器へpingを実行します。")
            btn_cols = st.columns(2)
            for i, (key, name) in enumerate(TARGET_NAMES.items()):
                with btn_cols[i % 2]:
                    already = st.session_state.checked[key]
                    label = f"{key}. {name}" + (" ✅" if already else "")
                    if st.button(f"{label} へ ping", key=f"btn_{key}",
                                 disabled=already, use_container_width=True):
                        ip = TARGET_IPS[key]
                        success = current_results[key] == "〇"
                        with st.spinner(f"{name}（{ip}）へ疎通確認中…"):
                            time.sleep(0.9)
                        st.session_state.ping_logs[key] = make_ping_log(name, ip, success)
                        st.session_state.checked[key] = True
                        st.toast(
                            f"{name} への疎通：{'成功 〇' if success else '失敗 ×'}",
                            icon="✅" if success else "🚫",
                        )
                        st.rerun()

            if st.session_state.ping_logs:
                with st.expander("pingコンソール出力を見る"):
                    for key, name in TARGET_NAMES.items():
                        if key in st.session_state.ping_logs:
                            st.code(st.session_state.ping_logs[key], language="text")

        with tab_lamp:
            st.caption("HUB本体のリンクランプ（点灯＝物理的に接続OK）を目視で確認します。")
            if not st.session_state.lamp_checked:
                if st.button("🔍 HUBのランプを確認する", type="secondary", use_container_width=True):
                    with st.spinner("HUB本体のランプを確認中…"):
                        time.sleep(0.9)
                    st.session_state.lamp_checked = True
                    st.toast("HUBのランプ状態を確認しました", icon="💡")
                    st.rerun()
            else:
                lamp_cols = st.columns(2)
                for i, (port_key, info) in enumerate(LAMP_PORTS.items()):
                    on = current_lamp[port_key] == "on"
                    icon = "🟢" if on else "🔴"
                    state = "点灯" if on else "消灯"
                    with lamp_cols[i % 2]:
                        st.markdown(
                            f'<div class="status-card" style="text-align:center;">'
                            f'<div style="font-size:22px;">{icon}</div>'
                            f'<div style="font-size:13px;color:#555;">{info["label"]}</div>'
                            f'<div style="font-weight:600;">{state}</div></div>',
                            unsafe_allow_html=True,
                        )
                st.caption("※ランプは物理的な接続状態のみを示します。正常点灯していても、"
                           "機器内部の故障で通信できない場合があります。")

        with tab_summary:
            st.markdown("**Ping結果一覧**")
            st.markdown(build_ping_table(current_results, st.session_state.checked), unsafe_allow_html=True)
            st.write("")
            st.markdown("**HUBランプ結果一覧**")
            st.markdown(build_lamp_table(current_lamp, st.session_state.lamp_checked), unsafe_allow_html=True)

        all_checked = all(st.session_state.checked.values())
        if not all_checked:
            remaining = [f"{k}.{TARGET_NAMES[k]}" for k in TARGET_NAMES if not st.session_state.checked[k]]
            st.caption(f"未確認：{' / '.join(remaining)}")

        # ---- ステップ5：原因の推理 ----
        if all_checked:
            st.divider()
            st.subheader("④ トラブルの原因を推理しよう")
            st.write("pingの結果とHUBランプの状態を組み合わせて、"
                     "想定される障害①〜④のうち、最も可能性が高いものを1つ選んでください。")

            if st.session_state.wrong_attempts >= 1 and not st.session_state.submitted:
                with st.expander("💡 ヒントを見る（考え方のポイント）"):
                    st.write(FAULT_SCENARIOS[st.session_state.current_fault]["hint"])

            options = ["-- 選択してください --"] + [
                f"{k} {v['cause']}" for k, v in FAULT_SCENARIOS.items()
            ]
            choice = st.selectbox("想定される障害", options, key="answer_select")
            choice_key = choice.split(" ")[0] if choice != "-- 選択してください --" else None

            if st.button("この原因で回答する", type="primary", disabled=(choice_key is None),
                         use_container_width=True):
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
                        "左のネットワーク構成図で、故障箇所が赤く表示されています。"
                        "pingの結果とHUBランプの状態を突き合わせることで、故障箇所を絞り込むことができます。"
                    )
                else:
                    st.error("❌ 残念、正解ではありません。")
                    st.markdown(
                        "**考え方のヒント**：pingで「×」になっている機器と「〇」になっている機器、"
                        "そしてHUBのランプの点灯／消灯パターンを見比べ、どこが壊れていると"
                        "ちょうどこの組み合わせになるかを、構成図をたどりながら考えてみましょう。"
                    )
                    if st.session_state.wrong_attempts >= 2:
                        st.info(f"💡 ヒント：{FAULT_SCENARIOS[correct]['hint']}")
                    if st.button("もう一度選び直す", use_container_width=True):
                        st.session_state.submitted = False
                        st.session_state.selected_answer = "-- 選択してください --"
                        st.rerun()