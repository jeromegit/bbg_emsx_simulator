import pandas as pd
import quickfix as fix


class OrderManager:
    def __init__(self):
        self.orders_df = pd.read_csv('oms_orders.csv')

    def save_orders(self):
        self.orders_df.to_csv('oms_orders.csv', index=False)

    def get_uuid_orders(self, uuid:str):
        orders = []
        for index, row in self.orders_df.iterrows():
            if str(row['uuid']) == uuid:
                orders.append(row)
#            print(f"Index: {index} uuid_col:{type(row['uuid'])} (uuid:{type(uuid)}-")
#        orders = self.orders_df[str(self.orders_df['uuid']) == uuid]
#        print(orders)

        return orders
