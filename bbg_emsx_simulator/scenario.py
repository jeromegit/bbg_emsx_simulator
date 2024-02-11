import re
from enum import Enum
from typing import Dict, Set, List, Tuple, Union


class Action(Enum):
    LOGON = "logon"
    RESERVE = "reserve"
    WAIT = "wait"
    ADD_ORDER = "add_order"
    UPDATE_ORDER = "update_order"
    DELETE_ORDER = "delete_order"
    SET = "set"


class ActionMandatoryKeys:
    keys_per_action: Dict[Action, Set[str]] = {
        Action.LOGON: {'50'},
        Action.RESERVE: {'50', '37', '38'}
    }


class KeyAlias:
    alias_to_actual: Dict[str, 'KeyAlias'] = {
        'uuid': '50',
        'orderid': '37',
        'qty': '38',
    }

    actual_to_alias: Dict[str, 'KeyAlias'] = {v: k for k, v in alias_to_actual.items()}

    @staticmethod
    def convert_aliases(key_values: Dict[str, str]) -> Dict[str, str]:
        converted_key_values: Dict[str, str] = {}
        for alias_key, value in key_values.items():
            key = KeyAlias.alias_to_actual.get(alias_key.lower(), alias_key)
            converted_key_values[key] = value

        return converted_key_values


class ActionLine:
    action: Action
    key_values: Dict[str, str]
    line_number: int
    label: str
    is_valid: bool

    action_keywords: Dict[str, Action] = {action.value: action for action in Action}

    def __init__(self, action_keyword: str, key_values: Dict[str, str], line_number: int, label: str):
        action = ActionLine.action_keywords.get(action_keyword.lower(), None)
        if action:
            self.action = action
        else:
            print(f"ERROR: action:{action_keyword} is not valid at line:{line_number}")
            self.is_valid = False
            return

        key_values = KeyAlias.convert_aliases(key_values)
        mandatory_keys = ActionMandatoryKeys.keys_per_action.get(action, [])
        for mandatory_key in mandatory_keys:
            if mandatory_key not in key_values:
                alias_key = KeyAlias.actual_to_alias.get(mandatory_key, None)
                if alias_key:
                    mandatory_key = mandatory_key + '/' + alias_key
                print(f"ERROR: key:{mandatory_key} is a mandatory key for action:{action.value} at line:{line_number}")
                self.is_valid = False
                return
        self.key_values = key_values

        self.label = label
        self.line_number = line_number
        self.is_valid = True

    def __str__(self):
        key_values_str = ", ".join(f"{key}={value}" for key, value in self.key_values.items())
        label_str = f'label:"{self.label}"' if self.label else "No label"
        return f"action:{self.action.value} | key_values:{key_values_str} | {label_str} | line_number:{self.line_number}"


class Scenario:
    action_lines: List[ActionLine] = []
    current_line: int = 0

    def __init__(self, scenario_file_path):
        with open(scenario_file_path) as fd:
            errors = 0
            line_number = 0
            for file_line in fd.readlines():
                line_number += 1
                if file_line.strip() and not file_line.startswith("#"):
                    action, key_values, label = self.parse_file_line(file_line)
                    if action:
                        action_line = ActionLine(action, key_values, line_number, label)
                        if action_line.is_valid:
                            self.add_action_line(action_line)
                        else:
                            errors += 1
                    else:
                        print(f"ERROR:`{file_line}` has an invalid format at line:{line_number}")
        if errors:
            print(f"\nERROR: processing file:{scenario_file_path} resulted in {errors} error(s). Exiting.")
        elif len(self.action_lines) == 0:
            print(f"ERROR: processing file:{scenario_file_path} didn't find any valid lines. Exiting.")
        else:
            return

        exit(1)

    def __str__(self):
        lines_str = "\n".join(str(line) for line in self.action_lines)
        return f"Scenario:\n{lines_str}"

    def add_action_line(self, action_line: ActionLine) -> None:
        self.action_lines.append(action_line)

    def parse_file_line(self, file_line: str) -> Tuple[Union[str, None], Union[Dict[str, str], None], Union[str, None]]:
        # action k1=v1 k2=v2 label="some text here"
        pattern = r'(\w+)\s+([a-zA-Z0-9_= ]+)(.*?)\s+(?:label="(.*?)")?'
        match = re.match(pattern, file_line)
        if match:
            action_keyword = match.group(1)
            key_value_pairs = dict(re.findall(r'(\w+)=(\w+)', match.group(2)))
            label = match.group(3)
            return action_keyword, key_value_pairs, label
        else:
            return None, None, None

    def play_next(self, to_next_wait: bool = True):
        while


if __name__ == "__main__":
    scenario_file_path = 'test_scenario.txt'
    scenario = Scenario(scenario_file_path)
    print(scenario)
