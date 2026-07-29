from typing import List, Optional, Tuple
from urllib.parse import quote
from datetime import datetime

from app.core.config import settings
from app.log import logger
from app.utils.http import AsyncRequestUtils, RequestUtils
from app.utils.string import StringUtils


class PirateBaySpider:
    """
    The Pirate Bay 公共资源站爬虫，基于 apibay.org JSON 接口搜索资源。

    Pirate Bay 原站 rarbg 已于 2023 年关闭，本爬虫使用 apibay.org 提供的
    官方 JSON 搜索接口，返回 info_hash、seeders、size 等结构化数据，
    磁力链由 info_hash 动态拼接标准 tracker 列表生成。
    """

    # 默认 API 地址
    _default_domain = "https://apibay.org/"
    # 标准 tracker 列表，用于拼接磁力链
    _trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.openbittorrent.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
    ]
    # 单页结果上限
    _size = 100
    _timeout = 15

    @classmethod
    def get_search_page_size(cls, keyword: Optional[str] = None) -> Optional[int]:
        """
        获取搜索接口单页容量。

        apibay.org 每次搜索返回固定上限的结果，不支持翻页。
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
        self._name = indexer.get("name") or "PirateBay"
        domain = indexer.get("domain") or self._default_domain
        if not str(domain).endswith("/"):
            domain = f"{domain}/"
        self._domain = domain
        self._proxy = settings.PROXY if indexer.get("proxy") else None
        self._ua = indexer.get("ua") or settings.USER_AGENT
        self._timeout = int(indexer.get("timeout") or self._timeout)

    @staticmethod
    def _parse_results(results: List[dict]) -> List[dict]:
        """
        解析 JSON 接口返回的种子列表。

        :param results: apibay.org 返回的 JSON 数组
        :return: 标准化的种子字典列表
        """
        torrents = []
        if not results:
            return torrents
        for item in results:
            info_hash = item.get("info_hash")
            title = item.get("name")
            if not info_hash or not title:
                continue
            # size 为字节数字符串，需安全转换
            try:
                size = int(item.get("size") or 0)
            except (ValueError, TypeError):
                size = 0
            # added 为 Unix 时间戳
            try:
                pubdate = datetime.fromtimestamp(
                    int(item.get("added") or 0)
                ).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, OSError):
                pubdate = ""
            torrents.append({
                "title": title,
                "description": f"Category: {item.get('category', '')} | User: {item.get('username', '')}",
                "enclosure": PirateBaySpider._build_magnet(info_hash, title),
                "page_url": f"https://thepiratebay.org/",
                "pubdate": pubdate,
                "size": size,
                "seeders": int(item.get("seeders") or 0),
                "peers": int(item.get("leechers") or 0),
                "grabs": 0,
                "downloadvolumefactor": 1,
                "uploadvolumefactor": 1,
            })
        return torrents

    @staticmethod
    def _build_magnet(info_hash: str, name: str) -> str:
        """
        由 info_hash 和名称拼接标准磁力链。

        :param info_hash: 种子哈希值
        :param name: 种子名称
        :return: 完整磁力链
        """
        trackers = "&".join(f"tr={quote(t, safe='')}" for t in PirateBaySpider._trackers)
        return f"magnet:?xt=urn:btih:{info_hash}&dn={quote(name, safe='')}&{trackers}"

    def search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        同步搜索资源。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码（接口不支持翻页，此处仅占位）
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # PirateBay 不支持中文搜索
            return True, []

        url = f"{self._domain}q.php?q={quote(keyword or '')}&cat=0"
        res = RequestUtils(ua=self._ua, proxies=self._proxy, timeout=self._timeout).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return True, []
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return True, []
        try:
            data = res.json()
        except Exception as err:
            logger.warn(f"{self._name} 解析搜索结果失败：{err}")
            return True, []
        if not isinstance(data, list):
            return True, []
        return False, self._parse_results(data)

    async def async_search(self, keyword: str, page: Optional[int] = 0) -> Tuple[bool, List[dict]]:
        """
        异步搜索资源。

        :param keyword: 搜索关键字（需为英文）
        :param page: 页码（接口不支持翻页，此处仅占位）
        :return: 是否出错, 种子列表
        """
        if StringUtils.is_chinese(keyword):
            # PirateBay 不支持中文搜索
            return True, []

        url = f"{self._domain}q.php?q={quote(keyword or '')}&cat=0"
        res = await AsyncRequestUtils(ua=self._ua, proxies=self._proxy, timeout=self._timeout).get_res(url)
        if not res:
            logger.warn(f"{self._name} 搜索失败，无法连接 {self._domain}")
            return True, []
        if res.status_code != 200:
            logger.warn(f"{self._name} 搜索失败，错误码：{res.status_code}")
            return True, []
        try:
            data = res.json()
        except Exception as err:
            logger.warn(f"{self._name} 解析搜索结果失败：{err}")
            return True, []
        if not isinstance(data, list):
            return True, []
        return False, self._parse_results(data)
