from typing import List, Optional, Tuple
from urllib.parse import quote, urljoin

from pyquery import PyQuery

from app.core.config import settings
from app.log import logger
from app.utils.http import AsyncRequestUtils, RequestUtils
from app.utils.string import StringUtils

# 尝试导入 curl_cffi，用于绕过 Cloudflare TLS 指纹检测
try:
    from curl_cffi import requests as _cfrequests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False


class LeetxSpider:
    """
    1337x 公共资源站爬虫，解析搜索结果列表并按需抓取详情页磁力链。

    1337x 为公开资源站，无需用户认证；列表页不含磁力链，需逐条访问详情页获取。
    为控制请求数量，默认只处理前 N 条结果。

    1337x 使用 Cloudflare 防护，当 curl_cffi 可用时通过 Chrome TLS 指纹模拟绕过；
    不可用时回退到 RequestUtils + 浏览器头，可能在部分网络环境下被 403 拦截。
    """

    # 默认域名（可通过 indexer.domain 指向可用镜像）
    _default_domain = "https://1337x.to/"
    # 单次搜索处理的结果上限，避免逐条抓取详情页时请求数失控
    _max_results = 30
    _timeout = 15
    # 浏览器 User-Agent，避免被 Cloudflare 前端检测拦截
    _browser_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # 浏览器请求头
    _browser_headers = {
        "User-Agent": _browser_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    @classmethod
    def get_search_page_size(cls, keyword: Optional[str] = None) -> Optional[int]:
        """
        获取搜索接口单页容量。

        1337x 关键字搜索不提供可靠的页码入口，返回 None 表示不自动翻页。
        """
        return None if keyword else cls._max_results

    def __init__(self, indexer: dict):
        """
        初始化爬虫参数。

        :param indexer: 索引器配置，需包含 domain；proxy/ua/timeout 可选
        """
        if not indexer:
            return
        self._indexerid = indexer.get("id")
        self._name = indexer.get("name") or "1337x"
        domain = indexer.get("domain") or self._default_domain
        if not str(domain).endswith("/"):
            domain = f"{domain}/"
        self._domain = domain
        self._proxy = settings.PROXY if indexer.get("proxy") else None
        # 始终使用浏览器 UA，覆盖 indexer 中传入的非浏览器 UA
        self._ua = self._browser_ua
        self._timeout = int(indexer.get("timeout") or self._timeout)

    def _get_proxy_dict(self) -> Optional[dict]:
        """
        将 settings.PROXY 转换为 curl_cffi 兼容的字典格式。
        """
        if not self._proxy:
            return None
        if isinstance(self._proxy, dict):
            https_proxy = self._proxy.get("https") or self._proxy.get("http")
            if https_proxy:
                return {"http": https_proxy, "https": https_proxy}
        elif isinstance(self._proxy, str):
            return {"http": self._proxy, "https": self._proxy}
        return None

    def _cf_get(self, url: str) -> Optional[object]:
        """
        使用 curl_cffi 发起 GET 请求，模拟 Chrome TLS 指纹绕过 Cloudflare。

        :param url: 请求地址
        :return: 响应对象或 None
        """
        if not _HAS_CURL_CFFI:
            return None
        try:
            proxies = self._get_proxy_dict()
            r = _cfrequests.get(
                url,
                impersonate="chrome",
                headers=self._browser_headers,
                proxies=proxies,
                timeout=self._timeout,
                verify=False,
                allow_redirects=True,
            )
            return r
        except Exception as err:
            logger.debug(f"{self._name} curl_cffi 请求失败：{url} - {err}")
            return None

    async def _cf_get_async(self, url: str) -> Optional[object]:
        """
        使用 curl_cffi 异步发起 GET 请求，模拟 Chrome TLS 指纹绕过 Cloudflare。

        :param url: 请求地址
        :return: 响应对象或 None
        """
        if not _HAS_CURL_CFFI:
            return None
        return self._cf_get(url)

    def _fetch_html(self, url: str) -> Optional[str]:
        """
        获取页面 HTML 文本，优先使用 curl_cffi 绕过 Cloudflare，回退到 RequestUtils。

        :param url: 页面地址
        :return: HTML 文本或 None
        """
        # 优先使用 curl_cffi 绕过 Cloudflare
        if _HAS_CURL_CFFI:
            r = self._cf_get(url)
            if r and r.status_code == 200:
                return r.text
            if r and r.status_code == 403:
                logger.warn(f"{self._name} Cloudflare 拦截（curl_cffi），错误码：{r.status_code}")
                return None
        # 回退到 RequestUtils + 浏览器头
        res = RequestUtils(
            headers=self._browser_headers, proxies=self._proxy, timeout=self._timeout
        ).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return None
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return None
        return res.text

    async def _fetch_html_async(self, url: str) -> Optional[str]:
        """
        异步获取页面 HTML 文本，优先使用 curl_cffi，回退到 AsyncRequestUtils。

        :param url: 页面地址
        :return: HTML 文本或 None
        """
        # 优先使用 curl_cffi 绕过 Cloudflare
        if _HAS_CURL_CFFI:
            r = self._cf_get(url)
            if r and r.status_code == 200:
                return r.text
            if r and r.status_code == 403:
                logger.warn(f"{self._name} Cloudflare 拦截（curl_cffi），错误码：{r.status_code}")
                return None
        # 回退到 AsyncRequestUtils + 浏览器头
        res = await AsyncRequestUtils(
            headers=self._browser_headers, proxies=self._proxy, timeout=self._timeout
        ).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return None
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return None
        return res.text

    def __build_search_url(self, keyword: str, page: Optional[int]) -> str:
        """
        构造搜索结果列表页地址。
        """
        page_num = int(page or 0) + 1
        if keyword:
            return f"{self._domain}search/{quote(keyword)}/{page_num}/"
        return f"{self._domain}sort/page-{page_num}/seeders/desc/"

    def __parse_list(self, html_text: str) -> List[dict]:
        """
        解析搜索结果列表页，提取标题、详情页地址及基础信息。
        """
        rows = []
        if not html_text:
            return rows
        try:
            doc = PyQuery(html_text)
        except Exception as err:
            logger.warn(f"{self._name} 列表页解析失败：{err}")
            return rows
        for tr in doc("table tbody tr").items():
            if len(rows) >= self._max_results:
                break
            try:
                # 详情页链接（href 形如 /torrent/123/xxx/）
                anchor = tr('a[href*="/torrent/"]').eq(0)
                href = anchor.attr("href") or ""
                title = (anchor.text() or "").strip()
                if not href or not title:
                    continue
                if not str(href).startswith("http"):
                    href = urljoin(self._domain, href)
                size_text = tr("td.size").clone()
                size_text.children().remove()
                size_str = (size_text.text() or "").strip()
                rows.append({
                    "title": title,
                    "page_url": href,
                    "size": StringUtils.num_filesize(size_str),
                    "seeders": self.__to_int(tr("td.seeds").text()),
                    "peers": self.__to_int(tr("td.leeches").text()),
                    "pubdate": (tr("td.coll-date").text() or "").strip(),
                })
            except Exception as err:
                logger.debug(f"{self._name} 解析单行失败：{err}")
                continue
        return rows

    @staticmethod
    def __to_int(text: Optional[str]) -> int:
        """
        将文本数字安全转为整数。
        """
        if not text:
            return 0
        num = "".join(ch for ch in str(text) if ch.isdigit())
        return int(num) if num else 0

    def __fetch_magnet(self, detail_url: str) -> Optional[str]:
        """
        抓取详情页中的磁力链。
        """
        html = self._fetch_html(detail_url)
        if not html:
            return None
        try:
            doc = PyQuery(html)
            magnet = doc('a[href^="magnet:"]').attr("href")
            return magnet or None
        except Exception as err:
            logger.debug(f"{self._name} 详情页磁力链解析失败：{err}")
            return None

    async def __async_fetch_magnet(self, detail_url: str) -> Optional[str]:
        """
        异步抓取详情页中的磁力链。
        """
        html = await self._fetch_html_async(detail_url)
        if not html:
            return None
        try:
            doc = PyQuery(html)
            magnet = doc('a[href^="magnet:"]').attr("href")
            return magnet or None
        except Exception as err:
            logger.debug(f"{self._name} 详情页磁力链解析失败：{err}")
            return None

    def search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        同步搜索资源，逐条抓取详情页补全磁力链。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # 1337x 不支持中文搜索
            return True, []

        url = self.__build_search_url(keyword, page)
        html = self._fetch_html(url)
        if html is None:
            return True, []

        rows = self.__parse_list(html)
        torrents = []
        for row in rows:
            magnet = self.__fetch_magnet(row.get("page_url"))
            if not magnet:
                continue
            torrents.append({
                "title": row.get("title"),
                "description": "",
                "enclosure": magnet,
                "page_url": row.get("page_url"),
                "pubdate": row.get("pubdate") or "",
                "size": row.get("size") or 0,
                "seeders": row.get("seeders") or 0,
                "peers": row.get("peers") or 0,
                "grabs": 0,
                "downloadvolumefactor": 1,
                "uploadvolumefactor": 1,
            })
        return False, torrents

    async def async_search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        异步搜索资源，逐条抓取详情页补全磁力链。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # 1337x 不支持中文搜索
            return True, []

        url = self.__build_search_url(keyword, page)
        html = await self._fetch_html_async(url)
        if html is None:
            return True, []

        rows = self.__parse_list(html)
        torrents = []
        for row in rows:
            magnet = await self.__async_fetch_magnet(row.get("page_url"))
            if not magnet:
                continue
            torrents.append({
                "title": row.get("title"),
                "description": "",
                "enclosure": magnet,
                "page_url": row.get("page_url"),
                "pubdate": row.get("pubdate") or "",
                "size": row.get("size") or 0,
                "seeders": row.get("seeders") or 0,
                "peers": row.get("peers") or 0,
                "grabs": 0,
                "downloadvolumefactor": 1,
                "uploadvolumefactor": 1,
            })
        return False, torrents
