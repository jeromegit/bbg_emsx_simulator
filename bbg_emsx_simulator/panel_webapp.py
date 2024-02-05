import re
import subprocess
import time
from collections import deque
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
TAIL_LINE_COUNT = 10

# -- Init
order_manager = OrderManager()
order_grid_df = order_manager.create_orders_df_copy()
last_tailed_log_line = ''


# -- Callbacks
def refresh(_):
    order_manager.read_orders_from_file()
    set_grid_order_df(order_manager.create_orders_df_copy())
    #    log_to_pane(f"Refresh: id:{id(order_grid_df)}:\n {order_grid_df}")
    last_update = order_manager.get_file_timestamp()
    log_to_pane(f"Order grid was refreshed from the file (last_update: {last_update})")


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


def xterm_highlight_str(string: str) -> str:
    return '\x1b[1;32m' + string + '\x1b[1;37m'


def tail_server_fix_log_in_terminal():
    global last_tailed_log_line
    # TODO. Need a more efficient way to do this. Remember the last file position and reread from it?
    command = f"grep -v '35=0' {FIX_SERVER_LOG_FILE_PATH} | tail -{TAIL_LINE_COUNT}"
    tailed_lines = run_command(command)
    tailed_lines = [line.replace('\001', '|') for line in tailed_lines if line]
    if last_tailed_log_line != tailed_lines[-1]:
        terminal.clear()
        highlighted_35 = [re.sub('(35=.)', lambda m: xterm_highlight_str(m.group(1)), line) for line in tailed_lines]
        terminal.write("\n".join(highlighted_35))
        last_tailed_log_line = tailed_lines[-1]


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
    order_grid = pn.widgets.Tabulator(order_grid_df, name='Table',
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


# -- Main starts here
# The panel module seems to work best when everything is defined global
tabulator_formatters = {
    'float': {'type': 'progress', 'max': 10},
    'bool': {'type': 'tickCross'}
}
bokeh_formatters = {
    'float': NumberFormatter(format='0.00000'),
    'bool': BooleanFormatter(),
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

pn.extension("tabulator",
             css_files=["https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"])
pn.extension('terminal')

title = pn.pane.Markdown(r"""
# OMS Order Manager
## Orders
""")
order_grid = create_order_grid(order_grid_df)

info_pane = pn.pane.HTML("Info.")

add_row_button = pn.widgets.Button(name='Add row', button_type='primary')
add_row_button.on_click(add_row)

refresh_button = pn.widgets.Button(name='Refresh')
refresh_button.on_click(refresh)

log_title = pn.pane.Markdown(f"## Server FIX Log (last {TAIL_LINE_COUNT} lines)")
terminal = pn.widgets.Terminal(
    "FIX server app log coming up here... (TBD)\n\n",
    options={"fontSize": 12},
    height=500, sizing_mode='stretch_width'
)

pn.state.add_periodic_callback(tail_server_fix_log_in_terminal, period=1_000)

table_theme = pn.widgets.Select(name='Select',
                                options=['simple', 'default', 'midnight', 'site', 'modern', 'bootstrap',
                                         'bootstrap4', 'materialize', 'semantic-ui', 'bulma'])
table_theme.param.watch(update_theme, 'value')

app = pn.Column(
    title,
    pn.Row(order_grid, info_pane),
    pn.Row(add_row_button, refresh_button),
    log_title,
    terminal,
)
app.servable()
