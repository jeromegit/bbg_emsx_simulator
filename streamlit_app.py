from typing import List

import streamlit as st
from pandas import DataFrame

from order_manager import OrderManager
from fix_application import FIXApplication

GRID_KEY = 'grid'
VALID_TICKERS:List[str] = FIXApplication.KNOWN_SYMBOLS_BY_TICKER.keys()

def create_data_editor(orders_df: DataFrame) -> DataFrame:
    # the columns names must match the ones in the csv file
    edited_df = st.data_editor(orders_df, key=GRID_KEY,
                               height=420,
                               use_container_width=True,
                               num_rows='dynamic',
                               column_config={
                                   "order_id": st.column_config.TextColumn(
                                   ),
                                   "uuid":st.column_config.NumberColumn(
                                       format="%d",
                                   ),
                                   "side": st.column_config.SelectboxColumn(
                                       options=OrderManager.SIDES
                                   ),
                                   "price": st.column_config.NumberColumn(
                                       format="$ %.2f",
                                   ),
                                   "symbol":st.column_config.SelectboxColumn(
                                       options=VALID_TICKERS,
                                   ),
                               },
                               hide_index=True,
                               )
    return edited_df


def process_edited_added_rows(orders_df: DataFrame, edited_df: DataFrame) -> None:
    edited_rows = st.session_state[GRID_KEY]["edited_rows"]
    added_rows = st.session_state[GRID_KEY]["added_rows"]
    initial_change_count = valid_change_count = len(edited_rows) + len(added_rows)
    edited_rows = st.session_state[GRID_KEY]["edited_rows"]
    for index, edited_columns in edited_rows.items():
        if 'order_id' in edited_columns or 'uuid' in edited_columns:
            current_order_id = orders_df.iloc[index]['order_id']
            st.error(
                f"Can't change order_id and UUID. Ignoring the changed row with current order_id:{current_order_id}")
            edited_df.iloc[int(index)] = orders_df.iloc[int(index)]
            valid_change_count -= 1

    if valid_change_count:
        order_manager.orders_df = edited_df
        order_manager.save_orders()

        order_manager.save_order_change_instructions(st.session_state[GRID_KEY])
        st.success('Orders saved/sent successfully!')
    else:
        if initial_change_count != 1:
            st.warning('No valid order left to save/send')


def main(order_manager: OrderManager) -> None:
    st.set_page_config(layout="wide")

    orders_df = order_manager.orders_df
    st.title('OMS Orders Management')
    edited_df = create_data_editor(orders_df)

    if st.button('Save/Send Changes'):
        # st.write(st.session_state[GRID_KEY])

        if len(st.session_state[GRID_KEY]["deleted_rows"]):
            st.error("Orders can't be deleted, just mark them as inactive. Ignoring all changes")
        else:
            valid_row_count = (len(st.session_state[GRID_KEY]["edited_rows"]) +
                               len(st.session_state[GRID_KEY]["added_rows"]))
            if valid_row_count == 0:
                st.warning("No change to save/send")
            else:
                process_edited_added_rows(orders_df, edited_df)

        st.button('Close')

    # TODO: add a button to stop server/client app, reset the state, and restart


if __name__ == "__main__":
    order_manager = OrderManager()
    main(order_manager)
