from functools import partial
from typing import List

import panel as pn
from bokeh.models.widgets.tables import NumberFormatter, BooleanFormatter, CheckboxEditor, NumberEditor, SelectEditor, \
    IntEditor
from pandas import DataFrame
from panel.models.tabulator import CellClickEvent

from fix_application import FIXApplication
from order_manager import OrderManager

GRID_KEY = 'grid'
VALID_TICKERS: List[str] = list(FIXApplication.KNOWN_SYMBOLS_BY_TICKER.keys())
PUSH_BUTTON = 'push'


def refresh(_):
    df = order_manager.read_orders_from_file()
    table.value = df


def add_row(df: DataFrame, table: str, _):
    new_row = [0, True, 0, '', 'Buy', 0, 0]
    df.loc[len(df)] = new_row
    OrderManager.normalize_order_df_col_types(df)
    table.value = df


def push_order_row(df: DataFrame, e: CellClickEvent):
    if e.column == PUSH_BUTTON:
        print("-------------------- PUSH ---------------------")
        edited_row_number = e.row
        edited_row = df.loc[edited_row_number]
        current_df = order_manager.read_orders_from_file()
        if len(current_df) - 1 < edited_row_number:
            print(f"New row:\n{edited_row}")
        else:
            current_row = current_df.loc[edited_row_number]
            print(f"Update row:\nCURRENT:\n{current_row}\nNEW\n{edited_row}")


def update_theme(e):
    table.theme = e.new


# -- Main starts here
# The panel module seems to work best when everything is defined global

order_manager = OrderManager()

edited_orders_df = order_manager.orders_df.copy()

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
    'side': SelectEditor(options=list(OrderManager.SIDES)),
}

pn.extension("tabulator",
             css_files=["https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"])
table = pn.widgets.Tabulator(edited_orders_df, name='Table',
                             theme='site',
                             formatters=bokeh_formatters,
                             editors=bokeh_editors,
                             buttons={PUSH_BUTTON: '<i class="fa fa-right-to-bracket"></i>'})
table.on_click(partial(push_order_row, edited_orders_df))

add_row_button = pn.widgets.Button(name='Add row', button_type='primary')
add_row_button.on_click(partial(add_row, edited_orders_df, table))

refresh_button = pn.widgets.Button(name='Refresh')
refresh_button.on_click(refresh)

terminal = pn.widgets.Terminal(
    "Welcome to the Panel Terminal!\nI'm based on xterm.js\n\n",
    options={"cursorBlink": True},
    height=300, sizing_mode='stretch_width'
)

table_theme = pn.widgets.Select(name='Select',
                                options=['simple', 'default', 'midnight', 'site', 'modern', 'bootstrap',
                                         'bootstrap4', 'materialize', 'semantic-ui', 'bulma'])
table_theme.param.watch(update_theme, 'value')

app = pn.Column(
    table,
    #    table_theme,
    add_row_button,
    refresh_button,
    terminal,
    #            pn.bind(add_row, add_row_button.clicks)
    # , args=tuple([table, orders_df])),
)

#
# 'simple'
# 'default'
# 'midnight'
# 'site'
# 'modern'
# 'bootstrap'
# 'bootstrap4'
# 'materialize'
# 'semantic-ui'
# 'bulma'
# Show the app
pn.serve(app)
