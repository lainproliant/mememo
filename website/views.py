from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse


# --------------------------------------------------------------------
@dataclass
class GlobalState:
    image_data: bytes | None = None


state = GlobalState()


# --------------------------------------------------------------------
def kitty_hello(request: HttpRequest):
    if state.image_data is None:
        with open("/opt/mememo/dancing-cat.gif", "rb") as infile:
            state.image_data = infile.read()
    return HttpResponse(state.image_data, content_type="image/gif")
