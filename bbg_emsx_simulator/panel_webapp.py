import re
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import List, Union, Any

import panel as pn
from bokeh.models.widgets.tables import NumberFormatter, BooleanFormatter, CheckboxEditor, NumberEditor, SelectEditor, \
    IntEditor
from pandas import DataFrame
from panel.models.tabulator import CellClickEvent

from fix_application import FIXApplication
from order_manager import OrderManager

FIX_SERVER_LOG_FILE_PATH = 'log/FIX.4.2-FIXSERVER-FIXCLIENT.messages.current.log'
VALID_TICKERS: List[str] = list(FIXApplication.KNOWN_SYMBOLS_BY_TICKER.keys())
VALID_SIDES: List[str] = list(OrderManager.SIDES)
PUSH_BUTTON = 'push'

# -- Init
order_manager = OrderManager()
order_grid_df = order_manager.create_orders_df_copy()
last_tailed_log_line = ''
last_order_file_timestamp = ''
fix_server_log_file_path = Path(FIX_SERVER_LOG_FILE_PATH)


# -- Callbacks
def refresh_callback(_):
    refresh_from_order_file()


def refresh_from_order_file():
    global last_order_file_timestamp
    order_file_timestamp = order_manager.get_file_timestamp()
    if last_order_file_timestamp < order_file_timestamp:
        last_order_file_timestamp = order_file_timestamp
        order_manager.read_orders_from_file()
        set_grid_order_df(order_manager.create_orders_df_copy())
        #    log_to_pane(f"Refresh: id:{id(order_grid_df)}:\n {order_grid_df}")
        log_to_pane(f"Order grid was refreshed from the file (last_update: {order_file_timestamp})")


def add_row(_):
    # TODO: prevent new add_row until any previously added row has been pushed
    global order_grid_df
    seconds_since_midnight = time.time() % 86400
    new_row = [seconds_since_midnight, True, 0, VALID_TICKERS[0], VALID_SIDES[0], 10000, 12.34]
    order_grid_df.loc[len(order_grid_df)] = new_row
    OrderManager.normalize_orders_df_col_types(order_grid_df)
    set_grid_order_df(order_grid_df)


#    log_to_pane(f"order_grid.value. id:{id(order_grid.value)}:\n {order_grid.value}")

def delete_row(_):
    # TODO: Allow to delete rows?
    pass


def log_to_pane(text: Union[str, Any]) -> None:
    if not isinstance(text, str):
        text = f"{text}"
    text = f"<pre>{text}</pre>"

    info_pane.object = text


def push_order_row(e: CellClickEvent):
    if e.column == PUSH_BUTTON:
        grid_row_number = e.row
        grid_row = order_grid_df.loc[grid_row_number]
        outcome = order_manager.update_or_add_row(grid_row_number, grid_row)
        log_to_pane(outcome)


def update_theme(e):
    order_grid.theme = e.new


def html_panel_css() -> str:
    html_panel_css = """<style>
    .color_35 {background-color: green}
    .color_37 {color: cyan}
    .color_50 {color: orange}
    .color_55 {color: yellow}

    div {
      white-space: pre;
      overflow-x: auto;
    }
    </style>"""

    return html_panel_css


def highlight_tags_in_html_lines(lines: List[str]) -> List[str]:
    hightlighted_lines: List[str] = []
    TAGS_TO_COLOR: set[int] = {35, 37, 50, 55}
    for line in lines:
        hightlighted_line = line
        for tag in TAGS_TO_COLOR:
            tag_span = f'<span class="color_{tag}">'
            hightlighted_line = re.sub(f'\|({tag}=[^|]+)', lambda m: f"|{tag_span}{m.group(1)}</span>",
                                       hightlighted_line)
        hightlighted_lines.append(hightlighted_line + "\n")

    return hightlighted_lines


def tail_server_fix_log_in_html_pane():
    global last_tailed_log_line, last_modified, last_log_line_count, current_modified

    log_line_count = log_line_count_slider.value
    load_lines = last_log_line_count is None or (last_log_line_count != log_line_count)
    if not load_lines:
        current_modified = fix_server_log_file_path.stat().st_mtime
        load_lines = current_modified != last_modified

    if load_lines:
        last_modified = current_modified
        last_log_line_count = log_line_count

        # TODO. Need a more efficient way to do this. Remember the last file position and reread from it?
        command = f"grep -v '35=0' {FIX_SERVER_LOG_FILE_PATH} | tail -{log_line_count}"
        tailed_lines = run_command(command)

        tailed_lines = [line.replace('\001', '|') for line in tailed_lines if line]
        hightlighted_lines = "".join(highlight_tags_in_html_lines(tailed_lines))
        html = f"""{html_panel_css()}<div>{hightlighted_lines}</div>"""
        html_pane.object = html


def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    if error:
        print(f"Error: {error}")
    return output.decode().split('\n')


def tail(filename, n=10):
    with open(filename, 'r') as f:
        return deque(f, n)


def create_order_grid(order_grid_df):
    bokeh_formatters = {
        'uuid': NumberFormatter(format='0'),
        'is_active': BooleanFormatter(),
    }

    bokeh_editors = {
        'order_id': IntEditor(),
        'is_active': CheckboxEditor(),
        'uuid': IntEditor(),
        'shares': IntEditor(),
        'price': NumberEditor(),
        'symbol': SelectEditor(options=VALID_TICKERS),
        'side': SelectEditor(options=VALID_SIDES),
    }

    order_grid = pn.widgets.Tabulator(order_grid_df,
                                      theme='site',
                                      formatters=bokeh_formatters,
                                      editors=bokeh_editors,
                                      buttons={PUSH_BUTTON: '<i class="fa fa-right-to-bracket"></i>'})
    order_grid.on_click(push_order_row)

    return order_grid


def set_grid_order_df(_grid_order_df: DataFrame) -> None:
    global order_grid_df
    order_grid_df = _grid_order_df
    order_grid.value = order_grid_df


# NOTE: The panel module seems to work best when everything is defined global
# -- Main starts here
pn.extension("tabulator",
             css_files=["https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"])

title = pn.pane.Markdown(r"""
# OMS Order Manager
## Orders
""")
order_grid = create_order_grid(order_grid_df)

info_pane = pn.pane.HTML("Info.")

add_row_button = pn.widgets.Button(name='Add row', button_type='primary')
add_row_button.on_click(add_row)

refresh_button = pn.widgets.Button(name='Refresh')
refresh_button.on_click(refresh_callback)

log_title = pn.pane.Markdown("## Server FIX Log ")

log_line_count_slider = pn.widgets.IntSlider(name='Last log line count', start=10, end=100, step=10, value=30)

html_pane_styles = {
    'background-color': 'black', 'color': 'white', 'font-size': '11px', 'font-family': 'monospace',
    'border': '2px solid black',
    'border-radius': '5px', 'padding': '10px'
}
html_pane = pn.pane.HTML("""(waiting for log...)""", styles=html_pane_styles)

# Init global vars used in the call back
last_tailed_log_line, last_order_file_timestamp, last_modified, last_log_line_count, current_modified = '', '', 0, 0, 0
pn.state.add_periodic_callback(refresh_from_order_file, period=1_000)
pn.state.add_periodic_callback(tail_server_fix_log_in_html_pane, period=1_000)

table_theme = pn.widgets.Select(name='Select',
                                options=['simple', 'default', 'midnight', 'site', 'modern', 'bootstrap',
                                         'bootstrap4', 'materialize', 'semantic-ui', 'bulma'])
table_theme.param.watch(update_theme, 'value')

app = pn.Column(
    title,
    pn.Row(order_grid, info_pane),
    pn.Row(add_row_button, refresh_button),
    log_title,
    log_line_count_slider,
    html_pane,
)
app.servable()
