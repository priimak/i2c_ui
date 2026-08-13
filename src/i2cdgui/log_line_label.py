from i2c_api.log import I2CTransactionElement
from pytide6 import RichTextLabel

from i2cdgui.i2c_log import i2c_log_message_to_str


class LogLineLabel(RichTextLabel):
    def __init__(self):
        super().__init__("<em>Last I2C operation:</em>")
        self.setStyleSheet("border: 1px solid black;")

    def set_log_message(self, log_message: str):
        self.setText(log_message)

    def set_i2c_log_message(self, log_message: list[I2CTransactionElement]):
        join = " ".join([i2c_log_message_to_str(e) for e in log_message])
        self.setText(join)
