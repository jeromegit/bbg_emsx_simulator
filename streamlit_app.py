import streamlit as st
from order_manager import OrderManager

order_manager = OrderManager()
orders_df = order_manager.orders_df
st.title('OMS Orders Management')

# the columns names must match the ones in the csv file
edited_df = st.data_editor(orders_df, key="grid",
                           num_rows='dynamic',
                           column_config={
                               "order_id": st.column_config.TextColumn(
                               ),
                               "side": st.column_config.SelectboxColumn(
                                   options=['Buy', 'Sell', 'Short']
                               ),
                               "price": st.column_config.NumberColumn(
                                   format="$ %.2f",
                               ),
                           },
                           hide_index=True,
                           )

if st.button('Save/Send Changes'):
    st.write("Here's the value in Session State:")
    edited_rows = st.session_state["grid"]["edited_rows"]
    for index, edited_columns in edited_rows.items():
        if 'order_id' in edited_columns or 'uuid' in edited_columns:
            current_order_id = orders_df.iloc[index]['order_id']
            st.error(
                f"Can't change order_id and UUID. Ignoring the changed row with current order_id:{current_order_id}")
        print(f"df_row:{edited_df.iloc[index]}")

    st.write(st.session_state["grid"])
    order_manager.orders_df = edited_df
    order_manager.save_orders()
    st.success('Orders saved successfully!')
