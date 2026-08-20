from collections.abc import Callable
from typing import Callable

from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import QMessageBox, QWidget
from pytide6 import CheckBox, ComboBox, Dialog, HBoxPanel, Label, PushButton, VBoxLayout, W
from pytide6.frame import HorizonalLine
from pytide6.inputs import LineEdit
from sprats.collections import Variable


class EvalExit(Exception):
    pass


class UserPromptDialog(Dialog):
    def __init__(self, title: str, vars: list[Variable]):
        super().__init__(None, windowTitle="User Input", modal=True)
        self.is_canceled = True

        def get_input_widget(variable: Variable) -> tuple[QWidget, Variable[str]]:
            if variable.type is bool:
                return CheckBox(reactive_variable=variable), Variable("")

            elif variable.valid_values is None:
                line_edit = LineEdit(reactive_variable=variable)
                line_edit_success = Variable[str]("")

                def mk_str_to_val[T](tr: Callable[[str], T]) -> Callable[[str], T]:
                    def str_to_val(value: str) -> T:
                        try:
                            output_value = tr(value)
                            line_edit_success.set_value("")
                            return output_value
                        except Exception:
                            line_edit_success.set_value(f'Invalid input value for "{variable.name}"')
                            return variable.value

                    return str_to_val

                if variable.type is float:

                    def val_to_str(value: float) -> str:
                        current_text = line_edit.text()
                        if current_text.strip() == "":
                            if value % 1 == 0:
                                return str(int(value))
                            else:
                                return str(value)
                        elif value != float(current_text):
                            return str(value)
                        else:
                            return current_text

                    variable.serializer = val_to_str
                    variable.deserializer = mk_str_to_val(float)
                    line_edit.setValidator(QDoubleValidator())

                elif variable.type is int:
                    variable.deserializer = mk_str_to_val(int)
                    line_edit.setValidator(QIntValidator())

                return line_edit, line_edit_success
            else:
                return ComboBox(reactive_variable=variable), Variable("")

        widgets = [HBoxPanel([Label(title)]), HorizonalLine()]
        self.inputs_success_status = []
        for variable in vars:
            widget, input_success_status = get_input_widget(variable)
            self.inputs_success_status.append(input_success_status)
            widgets.append(HBoxPanel([Label(f"{variable.name}"), widget, W(stretch=1)]))

        self.setLayout(
            VBoxLayout(
                widgets
                + [
                    W(stretch=1),
                    HorizonalLine(),
                    HBoxPanel(
                        [
                            W(stretch=1),
                            PushButton("Ok", parent=self, on_clicked=self.ok, auto_default=False),
                            PushButton("Cancel", parent=self, on_clicked=self.close, auto_default=False),
                        ]
                    ),
                ]
            )
        )

    def ok(self):
        for success_status in self.inputs_success_status:
            if success_status.value != "":
                QMessageBox.critical(None, "Error", success_status.value)
                return

        self.is_canceled = False
        self.close()


def mk_prompt_user(title: str):
    def prompt_user(*vs: Variable) -> tuple:
        dialog = UserPromptDialog(title, list(vs))
        dialog.exec()
        if dialog.is_canceled:
            raise EvalExit()
        if len(vs) == 1:
            return vs[0].value
        else:
            return tuple(v.value for v in vs)

    return prompt_user
