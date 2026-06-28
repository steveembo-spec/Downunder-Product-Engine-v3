from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dpe_v3.images.providers.base import ImageProvider


class MCASImageProvider(ImageProvider):
    name = "MCAS"

    extensions = [
        "jpg",
        "png",
        "jpeg",
        "webp",
    ]

    timeout_seconds = 4

    def search(self, product):
        sku = str(product.get("sku", "")).strip()

        if not sku:
            return None

        for extension in self.extensions:
            url = f"https://www.mcas.com.au/assets/full/{sku}.{extension}"

            if self.url_exists(url):
                return url

        return None

    def url_exists(self, url):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                method="HEAD",
            )

            with urlopen(request, timeout=self.timeout_seconds) as response:
                return 200 <= response.status < 400

        except HTTPError:
            return False

        except URLError:
            return False

        except TimeoutError:
            return False

        except Exception:
            return False