import re
from typing import List, Optional, Tuple
from urllib.parse import quote, urljoin

from pyquery import PyQuery

from app.core.config import settings
from app.log import logger
from app.utils.http import AsyncRequestUtils, RequestUtils
from app.utils.string import StringUtils


class BitSearchSpider:
    """
    BitSearch 公共资源站爬虫，列表页已包含磁力链，无需逐条访问详情页。

    BitSearch 为公开资源站，无需用户认证；使用浏览器 User-Agent 以兼容其前端检测。
    """

    # 默认域名（可通过 indexer.domain 指向可用镜像）
    _default_domain = "https://bitsearch.to/"
    # 单页结果上限
    _size = 100
    _timeout = 15
    # 浏览器 User-Agent，避免被前端检测拦截
    _browser_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def get_search_page_size(cls, keyword: Optional[str] = None) -> Optional[int]:
        """
        获取搜索接口单页容量。
        """
        return cls._size

    def __init__(self, indexer: dict):
        """
        初始化爬虫参数。

        :param indexer: 索引器配置，需包含 domain；proxy/ua/timeout 可选
        """
        if not indexer:
            return
        self._indexerid = indexer.get("id")
        self._name = indexer.get("name") or "BitSearch"
        domain = indexer.get("domain") or self._default_domain
        if not str(domain).endswith("/"):
            domain = f"{domain}/"
        self._domain = domain
        self._proxy = settings.PROXY if indexer.get("proxy") else None
        # 始终使用浏览器 UA，覆盖 indexer 中传入的非浏览器 UA
        self._ua = self._browser_ua
        self._timeout = int(indexer.get("timeout") or self._timeout)

    def _build_search_url(self, keyword: str, page: Optional[int]) -> str:
        """
        构造搜索结果列表页地址。
        """
        page_num = int(page or 0) + 1
        if keyword:
            return f"{self._domain}search?q={quote(keyword)}&page={page_num}"
        return f"{self._domain}trending?page={page_num}"

    @staticmethod
    def _to_int(text: Optional[str]) -> int:
        """
        将文本数字安全转为整数。
        """
        if not text:
            return 0
        match = re.search(r"\d+", str(text).replace(",", ""))
        return int(match.group()) if match else 0

    def _parse_list(self, html_text: str) -> List[dict]:
        """
        解析搜索结果列表页，从每个结果卡片中提取标题、磁力链与统计信息。
        """
        torrents = []
        if not html_text:
            return torrents
        try:
            doc = PyQuery(html_text)
        except Exception as err:
            logger.warn(f"{self._name} 列表页解析失败：{err}")
            return torrents
        # BitSearch 每个结果为一张白色卡片
        cards = doc("div.bg-white.rounded-lg")
        for card in cards.items():
            if len(torrents) >= self._size:
                break
            try:
                # 磁力链（已包含 tracker）
                magnet = card.find('a[href^="magnet:"]').eq(0).attr("href") or ""
                if not magnet:
                    continue
                # 标题：优先取 /torrent/ 链接文本，回退取磁力链 dn 参数
                title_link = card.find('a[href*="/torrent/"]').eq(0)
                title = (title_link.text() or "").strip()
                if not title:
                    # 从磁力链 dn 参数提取标题
                    dn_match = re.search(r"dn=([^&]+)", magnet)
                    if dn_match:
                        title = quote(dn_match.group(1), safe="%")
                if not title:
                    continue
                # 详情页地址
                detail_href = title_link.attr("href") or ""
                if detail_href and not str(detail_href).startswith("http"):
                    detail_href = urljoin(self._domain, detail_href)
                # 从卡片文本提取统计信息
                text = card.text() or ""
                # 大小（如 2.87 GB、500 MB）
                size_match = re.search(r"([\d.]+\s*(?:KB|MB|GB|TB))", text, re.IGNORECASE)
                size = StringUtils.num_filesize(size_match.group(1)) if size_match else 0
                # 做种数
                seeders = self._extract_stat(text, ["seeders", "seeds", "seed"])
                # 下载者数
                leechers = self._extract_stat(text, ["leechers", "leech", "peers"])
                # 下载次数
                grabs = self._extract_stat(text, ["downloads", "download"])
                # 日期（如 4/16/2024 或 2024-04-16）
                date_match = re.search(
                    r"(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
                    text,
                )
                torrents.append({
                    "title": title,
                    "description": "",
                    "enclosure": magnet,
                    "page_url": detail_href or magnet,
                    "pubdate": date_match.group(1) if date_match else "",
                    "size": size,
                    "seeders": seeders,
                    "peers": leechers,
                    "grabs": grabs,
                    "downloadvolumefactor": 1,
                    "uploadvolumefactor": 1,
                })
            except Exception as err:
                logger.debug(f"{self._name} 解析单个种子失败：{err}")
                continue
        return torrents

    @staticmethod
    def _extract_stat(text: str, labels: List[str]) -> int:
        """
        从卡片文本中按标签名提取前导数字。
        """
        for label in labels:
            match = re.search(rf"(\d[\d,]*)\s*{label}", text, re.IGNORECASE)
            if match:
                return BitSearchSpider._to_int(match.group(1))
        return 0

    def search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        同步搜索资源。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # BitSearch 不支持中文搜索
            return True, []

        url = self._build_search_url(keyword, page)
        # 使用浏览器级别的 headers 避免被前端拦截
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        res = RequestUtils(
            headers=headers, proxies=self._proxy, timeout=self._timeout
        ).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return True, []
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return True, []
        return False, self._parse_list(res.text)

    async def async_search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        异步搜索资源。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # BitSearch 不支持中文搜索
            return True, []

        url = self._build_search_url(keyword, page)
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        res = await AsyncRequestUtils(
            headers=headers, proxies=self._proxy, timeout=self._timeout
        ).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return True, []
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return True, []
        return False, self._parse_list(res.text)
