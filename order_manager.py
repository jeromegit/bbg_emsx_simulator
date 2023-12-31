import json
import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
from pandas import DataFrame, Series


class OrderManager:
    ORDERS_FILE_PATH = 'oms_orders.csv'
    ORDER_CHANGES_FILE_PATH = 'oms_order_changes.json'
    ORDER_CHANGES_TMP_FILE_PATH = 'oms_order_changes.json.tmp'
    COLUMN_DTYPE_PER_NAME = {
        'order_id': 'string',
        'is_active': 'bool',
        'uuid': 'Int32',
        'symbol': 'string',
        'side': 'category',
        'shares': 'Int32',
        'price': 'Float32',
    }
    SIDES = {'Buy': 1, 'Sell': 2, 'Short': 5}

    def __init__(self):
        self.orders_df = None
        self.last_order_changes_timestamp = datetime.now()
        self.read_orders_from_file()

    def read_orders_from_file(self) -> DataFrame:
        self.orders_df = pd.read_csv(OrderManager.ORDERS_FILE_PATH)

        for name, dtype in OrderManager.COLUMN_DTYPE_PER_NAME.items():
            self.orders_df[name] = self.orders_df[name].astype(dtype)

        return self.orders_df

    def save_orders(self):
        self.orders_df.to_csv(OrderManager.ORDERS_FILE_PATH, index=False)

    def get_orders_for_uuid(self, uuid: str) -> List[Series]:
        orders: List[Series] = []
        for index, row in self.orders_df.iterrows():
            if row['is_active'] and str(row['uuid']) == uuid:
                orders.append(row)

        return orders

    def save_order_change_instructions(self, order_changes: Dict[str, Dict[str, str]]):
        with open(OrderManager.ORDER_CHANGES_TMP_FILE_PATH, "w") as fp:
            json.dump(order_changes, fp, indent=4)

        os.rename(OrderManager.ORDER_CHANGES_TMP_FILE_PATH, OrderManager.ORDER_CHANGES_FILE_PATH)

    def check_and_process_order_change_instructions(self):
        file_mod_time = os.path.getmtime(OrderManager.ORDER_CHANGES_FILE_PATH)
        file_mod_datetime = datetime.fromtimestamp(file_mod_time)

        if file_mod_datetime > self.last_order_changes_timestamp:
            print("Detected order changes...")
            self.last_order_changes_timestamp = file_mod_datetime
            with open(OrderManager.ORDER_CHANGES_FILE_PATH, "r") as fp:
                order_changes = json.load(fp)
                self.process_order_changes(order_changes)

    def process_order_changes(self, order_changes: Dict[str, Dict[str, str]]):
        # the passed changes are tightly bound with streamlit's st.session_state after changing data in the data_editor
        # Example:
        # {
        #   "edited_rows": {
        #     "1": {
        #       "is_active": false
        #     },
        #     "2": {
        #       "symbol": "AAA"
        #     }
        #   },
        #   "added_rows": [
        #     {
        #       "order_id": "111",
        #       "is_active": true,
        #       "uuid": 888,
        #       "symbol": "DDDD",
        #       "side": "Buy",
        #       "shares": 1999,
        #       "price": 99.99
        #     }
        #   ],
        #   "deleted_rows": [
        #     5
        #   ]
        # }

        # It assumes that the changes have already been made and are already on the order file
        order_df = self.read_orders_from_file()

        edited_rows = order_changes["edited_rows"]
        for index, changes in edited_rows.items():
            order_row = order_df.iloc[int(index)]
            self.process_edited_added_row(order_row, changes, True)

        added_rows = order_changes["added_rows"]
        for added_row in added_rows:
            order_id = added_row['order_id']
            order_rows_for_order_id = order_df[order_df['order_id'] == order_id]
            if len(order_rows_for_order_id) >= 1:
                order_row = order_rows_for_order_id.iloc[0]
                self.process_edited_added_row(order_row, added_row, False)
            else:
                print(f"Can't find added row with order_id:{order_id}")

    def process_edited_added_row(self, order_row: Series, changes: Dict[str, str], is_edited: bool):
        # import here to avoid circular import dependencies
        from server_application import ServerApplication, MessageAction

        uuid = order_row['uuid']
        if ServerApplication.is_uuid_of_interest(uuid):
            if is_edited:
                if 'is_active' in changes:
                    message_action = MessageAction.NewOrder if changes['is_active'] else MessageAction.CancelOrder
                else:
                    message_action = MessageAction.ChangeOrder
            else:
                message_action = MessageAction.NewOrder

            ServerApplication.create_order_message(message_action, order_row, True)
        else:
            print(f"Changes requested for uuid:{uuid} but no interest there")
