from pytide6 import RichTextLabel

from i2cdgui.app import App


class OpenedProjectLabel(RichTextLabel):
    message_template = "<em>Project:</em> <b>{}</b>"

    def __init__(self, app: App):
        super().__init__(OpenedProjectLabel.message_template.format(""))
        app.update_project_selector_current_project = self.set_project_name
        self.setStyleSheet("border: 1px solid black;")

    def set_project_name(self, project_name: str):
        self.setText(OpenedProjectLabel.message_template.format(project_name))
