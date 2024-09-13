from app.Renderer import DefaultRenderer
from app.vhs import Vhs


class InterlacedRenderer(DefaultRenderer):
    @staticmethod
    def apply_main_effect(vhs: Vhs, frame1, frame2=None):
        raise NotImplementedError()
    
        # todo: rgm
        return frame