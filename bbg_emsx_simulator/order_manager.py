import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Union, Tuple

import pandas as pd
from numpy import int64
from pandas import DataFrame, Series


class OrderManager:
    ORDERS_FILE_PATH = 'oms_orders.csv'
    ORDER_CHANGES_FILE_PATH = 'oms_order_changes.json'
    ORDER_CHANGES_TMP_FILE_PATH = 'oms_order_changes.json.tmp'
    COLUMN_DTYPE_PER_NAME = {
        'order_id': 'Int64',
        'is_active': 'bool',
        'uuid': 'Int64',
        'symbol': 'string',
        'side': 'category',
        'shares': 'Int64',
        'price': 'Float32',
    }
    SIDES = {'Buy': 1, 'Sell': 2, 'Short': 5}

    def __init__(self):
        self.orders_df = None
        self.last_order_changes_timestamp = datetime.now()
        self.read_orders_from_file()

    def read_orders_from_file(self) -> DataFrame:
        self.orders_df = pd.read_csv(OrderManager.ORDERS_FILE_PATH)

        OrderManager.normalize_orders_col_types(self.orders_df)

        return self.orders_df

    def save_orders(self):
        self.orders_df.to_csv(OrderManager.ORDERS_FILE_PATH, index=False)

    def get_row_index_for_order_id(self, order_id: str) -> Union[int,None]:
        self.read_orders_from_file()
        try:
            order_id = int(order_id)
        except Exception as _:
            pass
        matching_row_indeces = self.orders_df.index[self.orders_df['order_id'] == order_id].tolist()
        if len(matching_row_indeces) == 1:
            row_index = matching_row_indeces[0]
            return row_index
        else:
            print(f"ERROR: can't find order with order_id:{order_id}")
            return None

    def update_order_shares(self, order_id: str, new_shares_increment: int) -> Union[int, None]:
        row_index = self.get_row_index_for_order_id(order_id)
        if row_index is not None:
            current_shares = self.orders_df.loc[row_index, 'shares']
            self.orders_df.loc[row_index, 'shares'] += new_shares_increment
            updated_shares = self.orders_df.loc[row_index, 'shares']
            self.save_orders()
            print(f"Updated order with order_id:{order_id} shares from {current_shares} to {updated_shares}")

            return updated_shares
        else:
            return None

    def get_order_shares(self, order_id: str) -> Union[int, None]:
        row_index = self.get_row_index_for_order_id(order_id)
        if row_index is not None:
            current_shares = self.orders_df.loc[row_index, 'shares']

            return current_shares
        else:
            return None

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

    def get_file_timestamp(self) -> str:
        last_modification_time = os.path.getmtime(OrderManager.ORDERS_FILE_PATH)
        last_modification_dt = datetime.fromtimestamp(last_modification_time)
        formatted_time = last_modification_dt.strftime("%Y-%m-%d %H:%M:%S")

        return formatted_time

    def check_and_process_order_change_instructions(self):
        if os.path.exists(OrderManager.ORDER_CHANGES_FILE_PATH):
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

        edited_rows = order_changes.get("edited_rows", {})
        for index, changes in edited_rows.items():
            order_row = order_df.iloc[int(index)]
            self.process_edited_added_row(order_row, changes, True)

        added_rows = order_changes.get("added_rows", [])
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

        # TODO: be smart about handling change in UUID since the order with the old UUID s/b canceled first
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

    def is_existing_order(self, saved_df: DataFrame, order_id: str) -> Tuple[bool, Union[int, None]]:
        matching_row_indeces = saved_df.index[saved_df['order_id'] == int(order_id)].tolist()
        if len(matching_row_indeces):
            return True, matching_row_indeces[0]
        else:
            return False, None

    def update_or_add_row(self, row_index: int, row: Series, should_populate_missing_values: bool = False) -> str:
        saved_df = self.read_orders_from_file()
        order_id = row['order_id']
        order_already_exits, found_row_index = self.is_existing_order(saved_df, order_id)
        if order_already_exits:
            row_index = found_row_index
            saved_df_row = saved_df.loc[row_index]
            if should_populate_missing_values:
                row = self.populate_missing_values(saved_df_row, row)
            row_diff = saved_df_row.compare(row, keep_equal=False)
            if len(row_diff):
                # print(f"Row change #{row_index}:\n{row_diff}")
                self.create_edited_added_row_instructions(dict({row_index: row_diff['other'].to_dict()}), False)
                self.orders_df.loc[row_index] = row
                outcome = f"Row:#{row_index} (order_id:{order_id}) has been modified."
            else:
                outcome = f"Row:#{row_index} (order_id:{order_id}) hasn't changed. Nothing to do."
        else:
            # print(f"New row (#{row_index}):\n{row}")
            self.create_edited_added_row_instructions(row.to_dict(), True)
            self.orders_df.loc[len(self.orders_df)] = row
            outcome = f"Row:#{row_index} (order_id:{order_id}) has been added."

        self.save_orders()

        return outcome

    def populate_missing_values(self, master_row: Series, row_with_missing_values: Series) -> Series:
        row = master_row.copy()
        for k, v in master_row.items():
            if k in row_with_missing_values:
                row[k] = row_with_missing_values[k]

        OrderManager.normalize_orders_col_types(row)
        return row

    # Replicate the way Streamlit does it (see process_order_changes() above)
    def create_edited_added_row_instructions(self, row: Dict, is_added: bool) -> None:
        instructions = {}
        if is_added:
            instructions['added_rows'] = [row]
        else:
            instructions['edited_rows'] = row

        self.save_order_change_instructions(instructions)

    def create_orders_df_copy(self) -> DataFrame:
        orders_df_copy = pickle.loads(pickle.dumps(self.orders_df))

        return orders_df_copy

    @staticmethod
    def normalize_orders_col_types(orders: Union[DataFrame, Series]):
        orders[['order_id', 'uuid', 'shares']] = orders[['order_id', 'uuid', 'shares']].astype(int64)
        orders['price'] = orders['price'].astype(float)
        orders['is_active'] = orders['is_active'].astype(bool)
