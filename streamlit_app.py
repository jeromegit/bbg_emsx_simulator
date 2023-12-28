import streamlit as st
import pandas as pd
from order_manager import OrderManager

st.title('OMS Orders Management')

order_manager = OrderManager()
orders_df = order_manager.orders_df

st.dataframe(orders_df)

if st.button('Save Changes'):
    order_manager.save_orders()
    st.success('Orders saved successfully!')