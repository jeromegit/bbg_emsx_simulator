import time
from typing import List, Union, Any

import panel as pn
from bokeh.models.widgets.tables import NumberFormatter, BooleanFormatter, CheckboxEditor, NumberEditor, SelectEditor, \
    IntEditor
from pandas import DataFrame
from panel.models.tabulator import CellClickEvent

from fix_application import FIXApplication
from order_manager import OrderManager

GRID_KEY = 'grid'
VALID_TICKERS: List[str] = list(FIXApplication.KNOWN_SYMBOLS_BY_TICKER.keys())
VALID_SIDES: List[str] = list(OrderManager.SIDES)
PUSH_BUTTON = 'push'

# -- Init
order_manager = OrderManager()
order_grid_df = order_manager.create_orders_df_copy()


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

log_title = pn.pane.Markdown("## FIX Log")
terminal = pn.widgets.Terminal(
    "FIX server app log coming up here... (TBD)\n\n",
    options={"cursorBlink": True},
    height=300, sizing_mode='stretch_width'
)

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
