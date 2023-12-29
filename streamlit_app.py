import streamlit as st
from order_manager import OrderManager

GRID_KEY = 'grid'


def main(order_manager: OrderManager) -> None:
    orders_df = order_manager.orders_df
    st.title('OMS Orders Management')
    # the columns names must match the ones in the csv file
    edited_df = st.data_editor(orders_df, key=GRID_KEY,
                               num_rows='dynamic',
                               column_config={
                                   "order_id": st.column_config.TextColumn(
                                   ),
                                   "side": st.column_config.SelectboxColumn(
                                       options=OrderManager.SIDES
                                   ),
                                   "price": st.column_config.NumberColumn(
                                       format="$ %.2f",
                                   ),
                               },
                               hide_index=True,
                               )

    if st.button('Save/Send Changes'):
        st.write("Here's the value in Session State:")
        st.write(st.session_state[GRID_KEY])

        if len(st.session_state[GRID_KEY]["deleted_rows"]):
            st.error("Orders can't be deleted, just mark them as inactive. Ignoring all changes")
            return

        edited_rows = st.session_state[GRID_KEY]["edited_rows"]
        added_rows = st.session_state[GRID_KEY]["added_rows"]
        valid_row_count = len(edited_rows) + len(added_rows)
        for index, edited_columns in edited_rows.items():
            if 'order_id' in edited_columns or 'uuid' in edited_columns:
                current_order_id = orders_df.iloc[index]['order_id']
                st.error(
                    f"Can't change order_id and UUID. Ignoring the changed row with current order_id:{current_order_id}")
                edited_df.iloc[int(index)] = orders_df.iloc[int(index)]
                valid_row_count -= 1

        if valid_row_count:
            order_manager.orders_df = edited_df
            order_manager.save_orders()

            order_manager.save_order_change_instructions(st.session_state[GRID_KEY])
            st.success('Orders saved/sent successfully!')
        else:
            st.warning('No valid order left to save/send')


if __name__ == "__main__":
    order_manager = OrderManager()
    main(order_manager)
