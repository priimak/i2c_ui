from pytide6 import VBoxPanel, W, HBoxPanel, PushButton, Label, ComboBox
from pytide6.inputs import LineEdit

from i2cdgui.app import App


class AddrSelector(ComboBox):
    def __init__(self, app: App):
        super().__init__()
        self.app = app

    def scan(self) -> None:
        addrs = [f"{a:X}" for a in self.app.scan()]
        self.clear()
        self.addItems(addrs)


class SpeedSelector(ComboBox):
    def __init__(self, app: App):
        super().__init__(items=["100 KHz", "400 KHz"], current_selection=app.persistence.config.get_by_xpath("/speed"))
        self.app = app

        def change_speed(new_speed: str) -> None:
            self.app.i2c.setspeed(int(new_speed[0:3]))
            self.setCurrentText(f"{self.app.i2c.speed}")
            self.app.persistence.config.set_by_xpath("/speed", self.currentText())

        self.currentTextChanged.connect(change_speed)


class PullUpResistorSelector(ComboBox):
    def __init__(self, app: App):
        super().__init__(items=["disabled", "2.2K", "4.3K", "1.5K", "4.7K", "1.5K", "2.2K", "1.1K"],
                         current_selection=app.persistence.config.get_by_xpath("/pullup"))
        self.app = app
        self.values = [self.itemText(i) for i in range(self.count())]
        self.setCurrentText(self.values[self.app.i2c.pullups & 7])

        def change_pullup_value(new_resistance: str) -> None:
            code = self.values.index(new_resistance)
            self.app.i2c.setpullups(code | (code << 3))

        self.currentTextChanged.connect(change_pullup_value)


class CommandsPanel(VBoxPanel):
    def __init__(self, app: App):
        super().__init__()
        self.addr_selector = AddrSelector(app)
        self.speed_selector = SpeedSelector(app)
        self.pullup_selector = PullUpResistorSelector(app)
        self.addWidget(
            HBoxPanel([
                W(Label(""), stretch=1), Label("I2C Device Address"), self.addr_selector,
                PushButton("Scan", on_clicked=self.addr_selector.scan), Label("  |  "),
                Label("Speed"), self.speed_selector, Label("  |  "),
                Label("Pullups"), self.pullup_selector,
                W(Label(""), stretch=1)
            ])
        )

        panel = VBoxPanel([HBoxPanel(
            [PushButton("Read Register"), Label(" Addr:"), LineEdit(), Label(" Num Bytes:"),
             ComboBox(items=["1", "2", "3", "4"]), W(Label(""), stretch=1)]), HBoxPanel(
            [PushButton("Write Register"), Label(" Addr:"), LineEdit(), Label(" Value:"),
             LineEdit(), Label(" Num Bytes:"), ComboBox(items=["1", "2", "3", "4"]), W(Label(""), stretch=1)])],
            margins=0)
        self.addWidget(HBoxPanel([W(Label(""), stretch=1), panel, W(Label(""), stretch=1)]))
