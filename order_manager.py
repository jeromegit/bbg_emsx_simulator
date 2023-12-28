import pandas as pd
import quickfix as fix


class OrderManager:
    def __init__(self):
        self.orders_df = pd.read_csv('oms_orders.csv')

        # set column type
        column_dtype_per_name = {
            'order_id': 'string',
            'is_active': 'bool',
            'uuid': 'Int32',
            'symbol': 'string',
            'side': 'category',
            'shares': 'Int32',
            'price': 'Float32',
        }
        for name, dtype in column_dtype_per_name.items():
            self.orders_df[name] = self.orders_df[name].astype(dtype)

    def save_orders(self):
        self.orders_df.to_csv('oms_orders.csv', index=False)

    def get_orders_for_uuid(self, uuid: str):
        orders = []
        for index, row in self.orders_df.iterrows():
            if row['is_active'] and str(row['uuid']) == uuid:
                orders.append(row)

        return orders
