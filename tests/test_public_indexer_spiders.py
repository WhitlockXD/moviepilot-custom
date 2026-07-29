"""内置公共资源站爬虫与搜索链注入的单元测试。

覆盖三个公共资源站爬虫（PirateBay / 1337x / BitSearch）的解析逻辑、
中文关键字守卫、IndexerModule 公共索引器注入，以及 SearchChain 的
中英转换与站点关键字计算辅助方法。全部 mock，零真实网络。
"""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.chain.search import SearchChain
from app.core.context import MediaInfo
from app.modules.indexer import IndexerModule, SPIDER_PARSER_CLASSES
from app.modules.indexer.spider.piratebay import PirateBaySpider
from app.modules.indexer.spider.leetx import LeetxSpider
from app.modules.indexer.spider.bitsearch import BitSearchSpider
from app.schemas.types import MediaType


# ────────────────────── 辅助构造 ──────────────────────


def _make_response(json_data=None, text: str = "", status_code: int = 200):
    """构造模拟 HTTP 响应对象。"""
    res = Mock()
    res.status_code = status_code
    res.text = text
    # 注意：空列表 [] 是合法的 JSON 响应，不能用 or 短路
    res.json.return_value = json_data if json_data is not None else {}
    return res


def _piratebay_indexer(**kwargs):
    """构造 PirateBay 爬虫所需的最小索引器配置。"""
    base = {
        "id": None,
        "name": "PirateBay",
        "domain": "https://apibay.org/",
        "parser": "PirateBaySpider",
        "language": "en",
        "public": True,
        "pri": 0,
        "proxy": False,
        "ua": "test-ua",
        "cookie": None,
        "timeout": 15,
    }
    base.update(kwargs)
    return base


def _leetx_indexer(**kwargs):
    """构造 1337x 爬虫所需的最小索引器配置。"""
    base = {
        "id": None,
        "name": "1337x",
        "domain": "https://1337x.to/",
        "parser": "LeetxSpider",
        "language": "en",
        "public": True,
        "pri": 0,
        "proxy": False,
        "ua": "test-ua",
        "cookie": None,
        "timeout": 15,
    }
    base.update(kwargs)
    return base


def _bitsearch_indexer(**kwargs):
    """构造 BitSearch 爬虫所需的最小索引器配置。"""
    base = {
        "id": None,
        "name": "BitSearch",
        "domain": "https://bitsearch.to/",
        "parser": "BitSearchSpider",
        "language": "en",
        "public": True,
        "pri": 0,
        "proxy": False,
        "ua": "test-ua",
        "cookie": None,
        "timeout": 15,
    }
    base.update(kwargs)
    return base


# ────────────────────── PirateBaySpider ──────────────────────


class TestPirateBaySpider:
    """PirateBay 公共资源站爬虫测试。"""

    _API_RESPONSE = [
        {
            "id": "1",
            "name": "Movie.2024.1080p.BluRay",
            "info_hash": "abc123def456",
            "leechers": "10",
            "seeders": "100",
            "size": "17179869184",
            "added": "1705312800",
            "category": "Video > Movies",
            "username": "uploader1",
        },
        {
            "id": "2",
            "name": "Another.Movie.2023.720p",
            "info_hash": "xyz789ghi012",
            "leechers": "5",
            "seeders": "50",
            "size": "0",
            "added": "0",
            "category": "Video > Movies",
            "username": "uploader2",
        },
        {
            # 缺少 info_hash，应被跳过
            "id": "3",
            "name": "No Hash",
            "seeders": "1",
        },
    ]

    def test_chinese_keyword_returns_empty(self):
        """中文关键字应被跳过，返回错误标志与空列表。"""
        spider = PirateBaySpider(_piratebay_indexer())
        error_flag, results = spider.search(keyword="流浪地球", page=0)
        assert error_flag is True
        assert results == []

    def test_async_chinese_keyword_returns_empty(self):
        """异步搜索中文关键字同样应被跳过。"""
        spider = PirateBaySpider(_piratebay_indexer())
        error_flag, results = asyncio.run(spider.async_search(keyword="流浪地球", page=0))
        assert error_flag is True
        assert results == []

    def test_parses_torrent_results(self):
        """正常 JSON 响应应解析为标准种子字典列表。"""
        search_response = _make_response(json_data=self._API_RESPONSE)
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = search_response
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert len(results) == 2
        torrent = results[0]
        assert torrent["title"] == "Movie.2024.1080p.BluRay"
        assert "magnet:?xt=urn:btih:abc123def456" in torrent["enclosure"]
        assert torrent["page_url"] == "https://thepiratebay.org/"
        assert torrent["seeders"] == 100
        assert torrent["peers"] == 10
        assert torrent["downloadvolumefactor"] == 1
        assert torrent["uploadvolumefactor"] == 1
        assert torrent["size"] > 0

    def test_parses_second_result(self):
        """第二条结果中 size 和 pubdate 为 0 时也应正常解析。"""
        search_response = _make_response(json_data=self._API_RESPONSE)
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = search_response
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert len(results) == 2
        second = results[1]
        assert second["title"] == "Another.Movie.2023.720p"
        assert "magnet:?xt=urn:btih:xyz789ghi012" in second["enclosure"]
        assert second["size"] == 0

    def test_empty_results(self):
        """搜索结果为空列表时应正常返回空列表。"""
        empty_response = _make_response(json_data=[])
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = empty_response
            error_flag, results = spider.search(keyword="NonExistentMovie", page=0)

        assert error_flag is False
        assert results == []

    def test_non_list_response_returns_error(self):
        """返回非 JSON 数组时应返回错误。"""
        error_response = _make_response(json_data={"error": "some error"})
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = error_response
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is True
        assert results == []

    def test_connection_failure_returns_error(self):
        """连接失败时应返回错误标志。"""
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = None
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is True
        assert results == []

    def test_async_parses_results(self):
        """异步搜索应正确解析结果。"""
        search_response = _make_response(json_data=self._API_RESPONSE)
        spider = PirateBaySpider(_piratebay_indexer())
        with patch(
            "app.modules.indexer.spider.piratebay.AsyncRequestUtils"
        ) as mock_au:
            mock_instance = mock_au.return_value
            mock_instance.get_res = AsyncMock(return_value=search_response)
            error_flag, results = asyncio.run(spider.async_search(keyword="Inception", page=0))

        assert error_flag is False
        assert len(results) == 2

    def test_get_search_page_size(self):
        """get_search_page_size 应返回固定页容量。"""
        assert PirateBaySpider.get_search_page_size() == 100
        assert PirateBaySpider.get_search_page_size(keyword="test") == 100


# ────────────────────── LeetxSpider ──────────────────────


class TestLeetxSpider:
    """1337x 公共资源站爬虫测试。"""

    _LIST_HTML = """
    <html><body>
    <table>
      <tbody>
        <tr>
          <td class="name">
            <a href="/torrent/123/movie-2024-1080p/">Movie.2024.1080p.BluRay</a>
          </td>
          <td class="size">4.3 GB</td>
          <td class="seeds">150</td>
          <td class="leeches">8</td>
          <td class="coll-date">Jan. 15th 2024</td>
        </tr>
        <tr>
          <td class="name">
            <a href="/torrent/456/another-movie/">Another.Movie.2023.720p</a>
          </td>
          <td class="size">2.1 GB</td>
          <td class="seeds">50</td>
          <td class="leeches">3</td>
          <td class="coll-date">Dec. 1st 2023</td>
        </tr>
      </tbody>
    </table>
    </body></html>
    """

    _DETAIL_HTML_1 = """
    <html><body>
      <a href="magnet:?xt=urn:btih:detail-hash-123">Download Magnet</a>
    </body></html>
    """

    _DETAIL_HTML_2 = """
    <html><body>
      <a href="magnet:?xt=urn:btih:detail-hash-456">Magnet Link</a>
    </body></html>
    """

    def test_chinese_keyword_returns_empty(self):
        """中文关键字应被跳过。"""
        spider = LeetxSpider(_leetx_indexer())
        error_flag, results = spider.search(keyword="流浪地球", page=0)
        assert error_flag is True
        assert results == []

    def test_parses_list_and_fetches_magnet(self):
        """应解析列表页并逐条抓取详情页获取磁力链。"""
        spider = LeetxSpider(_leetx_indexer())
        with patch.object(spider, "_fetch_html") as mock_fetch:
            mock_fetch.side_effect = [
                self._LIST_HTML,
                self._DETAIL_HTML_1,
                self._DETAIL_HTML_2,
            ]
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert len(results) == 2
        assert results[0]["title"] == "Movie.2024.1080p.BluRay"
        assert results[0]["enclosure"] == "magnet:?xt=urn:btih:detail-hash-123"
        assert results[0]["page_url"] == "https://1337x.to/torrent/123/movie-2024-1080p/"
        assert results[0]["seeders"] == 150
        assert results[0]["peers"] == 8
        assert results[0]["downloadvolumefactor"] == 1
        assert results[1]["enclosure"] == "magnet:?xt=urn:btih:detail-hash-456"

    def test_empty_html_returns_empty(self):
        """空 HTML 应返回空列表且无错误。"""
        spider = LeetxSpider(_leetx_indexer())
        with patch.object(spider, "_fetch_html") as mock_fetch:
            mock_fetch.return_value = ""
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert results == []

    def test_detail_fetch_failure_skips_row(self):
        """详情页请求失败时该行应被跳过。"""
        spider = LeetxSpider(_leetx_indexer())
        with patch.object(spider, "_fetch_html") as mock_fetch:
            # 列表页成功，两个详情页返回 None
            mock_fetch.side_effect = [self._LIST_HTML, None, None]
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert results == []

    def test_list_fetch_failure_returns_error(self):
        """列表页获取失败时应返回错误标志。"""
        spider = LeetxSpider(_leetx_indexer())
        with patch.object(spider, "_fetch_html") as mock_fetch:
            mock_fetch.return_value = None
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is True
        assert results == []

    def test_get_search_page_size_keyword_returns_none(self):
        """关键字搜索应返回 None 表示不自动翻页。"""
        assert LeetxSpider.get_search_page_size(keyword="test") is None

    def test_get_search_page_size_browse_returns_max(self):
        """浏览模式（无关键字）应返回结果上限。"""
        assert LeetxSpider.get_search_page_size() == 30


# ────────────────────── BitSearchSpider ──────────────────────


class TestBitSearchSpider:
    """BitSearch 公共资源站爬虫测试。"""

    _LIST_HTML = """
    <html><body>
      <div class="bg-white rounded-lg">
        <a href="/torrent/123/test-movie/">Test Movie 2024 1080p</a>
        <a href="magnet:?xt=urn:btih:bs-hash-123&dn=Test.Movie.2024.1080p">Magnet</a>
        <span>4.3 GB</span>
        <span>200 seeders</span>
        <span>15 leechers</span>
        <span>50 downloads</span>
        <span>2024-01-15</span>
      </div>
      <div class="bg-white rounded-lg">
        <a href="/torrent/456/another/">Another Movie 2023 720p</a>
        <a href="magnet:?xt=urn:btih:bs-hash-456&dn=Another.Movie.2023.720p">Magnet</a>
        <span>2.1 GB</span>
        <span>80 seeders</span>
        <span>5 leechers</span>
        <span>30 downloads</span>
        <span>2023-12-01</span>
      </div>
      <div class="bg-white rounded-lg">
        <a href="/torrent/789/no-magnet/">No Magnet Here</a>
        <span>1.0 GB</span>
        <span>10 seeders</span>
      </div>
    </body></html>
    """

    def test_chinese_keyword_returns_empty(self):
        """中文关键字应被跳过。"""
        spider = BitSearchSpider(_bitsearch_indexer())
        error_flag, results = spider.search(keyword="流浪地球", page=0)
        assert error_flag is True
        assert results == []

    def test_parses_list_with_magnet(self):
        """列表页应直接解析出磁力链，无需逐条访问详情页。"""
        list_response = _make_response(text=self._LIST_HTML, status_code=200)
        spider = BitSearchSpider(_bitsearch_indexer())
        with patch(
            "app.modules.indexer.spider.bitsearch.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = list_response
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert len(results) == 2
        assert results[0]["title"] == "Test Movie 2024 1080p"
        assert results[0]["enclosure"] == "magnet:?xt=urn:btih:bs-hash-123&dn=Test.Movie.2024.1080p"
        assert results[0]["page_url"] == "https://bitsearch.to/torrent/123/test-movie/"
        assert results[0]["seeders"] == 200
        assert results[0]["peers"] == 15
        assert results[0]["grabs"] == 50
        assert results[0]["downloadvolumefactor"] == 1
        assert results[0]["uploadvolumefactor"] == 1
        assert results[1]["enclosure"] == "magnet:?xt=urn:btih:bs-hash-456&dn=Another.Movie.2023.720p"
        assert results[1]["seeders"] == 80
        assert results[1]["peers"] == 5

    def test_empty_html_returns_empty(self):
        """空 HTML 应返回空列表。"""
        empty_response = _make_response(text="", status_code=200)
        spider = BitSearchSpider(_bitsearch_indexer())
        with patch(
            "app.modules.indexer.spider.bitsearch.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = empty_response
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is False
        assert results == []

    def test_connection_failure_returns_error(self):
        """连接失败时应返回错误标志。"""
        spider = BitSearchSpider(_bitsearch_indexer())
        with patch(
            "app.modules.indexer.spider.bitsearch.RequestUtils"
        ) as mock_ru:
            mock_instance = mock_ru.return_value
            mock_instance.get_res.return_value = None
            error_flag, results = spider.search(keyword="Inception", page=0)

        assert error_flag is True
        assert results == []

    def test_async_parses_results(self):
        """异步搜索应正确解析结果。"""
        list_response = _make_response(text=self._LIST_HTML, status_code=200)
        spider = BitSearchSpider(_bitsearch_indexer())
        with patch(
            "app.modules.indexer.spider.bitsearch.AsyncRequestUtils"
        ) as mock_au:
            mock_instance = mock_au.return_value
            mock_instance.get_res = AsyncMock(return_value=list_response)
            error_flag, results = asyncio.run(spider.async_search(keyword="Inception", page=0))

        assert error_flag is False
        assert len(results) == 2

    def test_get_search_page_size(self):
        """get_search_page_size 应返回固定页容量。"""
        assert BitSearchSpider.get_search_page_size() == 100
        assert BitSearchSpider.get_search_page_size(keyword="test") == 100


# ────────────────────── IndexerModule.get_public_indexers ──────────────────────


class TestPublicIndexers:
    """IndexerModule 公共索引器注入测试。"""

    def test_returns_three_indexers(self):
        """get_public_indexers 应返回三个内置公共站点。"""
        indexers = IndexerModule.get_public_indexers()
        assert len(indexers) == 3

    def test_all_have_no_id_and_public_flag(self):
        """公共索引器 id 应为 None，public 标记应为 True。"""
        for idx in IndexerModule.get_public_indexers():
            assert idx["id"] is None
            assert idx["public"] is True
            assert idx["language"] == "en"
            assert idx["cookie"] is None

    def test_parser_matches_spider_classes(self):
        """每个公共索引器的 parser 应在 SPIDER_PARSER_CLASSES 中注册。"""
        for idx in IndexerModule.get_public_indexers():
            assert idx["parser"] in SPIDER_PARSER_CLASSES

    def test_indexer_names(self):
        """公共索引器名称应正确。"""
        names = {idx["name"] for idx in IndexerModule.get_public_indexers()}
        assert names == {"PirateBay", "1337x", "BitSearch"}

    def test_domains_are_valid_urls(self):
        """所有公共索引器域名应以 https:// 开头并以 / 结尾。"""
        for idx in IndexerModule.get_public_indexers():
            domain = idx["domain"]
            assert domain.startswith("https://")
            assert domain.endswith("/")


# ────────────────────── SearchChain 辅助方法 ──────────────────────


def _build_search_chain():
    """构造隔离的 SearchChain 实例，避免依赖真实模块管理器。"""
    chain = object.__new__(SearchChain)
    chain.pluginmanager = Mock()
    chain.modulemanager = Mock()
    chain.messagehelper = Mock()
    chain.eventmanager = Mock()
    return chain


class TestPublicIndexerEnabled:
    """公共索引器开关逻辑测试。"""

    def test_defaults_true_when_unconfigured(self):
        """未配置时应默认启用。"""
        chain = _build_search_chain()
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper:
            mock_oper.return_value.get.return_value = None
            assert chain._public_indexer_enabled() is True

    def test_false_when_explicitly_disabled(self):
        """显式设为 False 时应禁用。"""
        chain = _build_search_chain()
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper:
            mock_oper.return_value.get.return_value = False
            assert chain._public_indexer_enabled() is False

    def test_true_when_explicitly_enabled(self):
        """显式设为 True 时应启用。"""
        chain = _build_search_chain()
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper:
            mock_oper.return_value.get.return_value = True
            assert chain._public_indexer_enabled() is True


class TestHasEnglishIndexer:
    """英文站点检测逻辑测试。"""

    def test_detects_english_site(self):
        """含 language=en 的站点应返回 True。"""
        sites = [{"name": "PT站", "language": "zh"}, {"name": "1337x", "language": "en"}]
        assert SearchChain._has_english_indexer(sites) is True

    def test_no_english_site(self):
        """不含英文站点时应返回 False。"""
        sites = [{"name": "PT站", "language": "zh"}]
        assert SearchChain._has_english_indexer(sites) is False

    def test_empty_list(self):
        """空列表应返回 False。"""
        assert SearchChain._has_english_indexer([]) is False

    def test_none_language(self):
        """language 缺失时应返回 False。"""
        sites = [{"name": "Unknown", "language": None}]
        assert SearchChain._has_english_indexer(sites) is False


class TestSiteSearchKeyword:
    """站点搜索关键字计算逻辑测试。"""

    def test_imdbid_area_returns_imdb_id(self):
        """imdbid 搜索区域应返回媒体的 IMDb ID。"""
        media = MediaInfo(title="Test", imdb_id="tt1234567")
        result = SearchChain._site_search_keyword(
            site={"language": "en"},
            keyword="original",
            mediainfo=media,
            area="imdbid",
            english_keyword="English Title",
        )
        assert result == "tt1234567"

    def test_english_site_returns_english_keyword(self):
        """英文站点应使用英文译名。"""
        result = SearchChain._site_search_keyword(
            site={"language": "en"},
            keyword="流浪地球",
            mediainfo=None,
            area="title",
            english_keyword="The Wandering Earth",
        )
        assert result == "The Wandering Earth"

    def test_non_english_site_returns_original_keyword(self):
        """非英文站点应使用原始关键字。"""
        result = SearchChain._site_search_keyword(
            site={"language": "zh"},
            keyword="流浪地球",
            mediainfo=None,
            area="title",
            english_keyword="The Wandering Earth",
        )
        assert result == "流浪地球"

    def test_english_site_without_english_keyword(self):
        """英文站点但无英文译名时应回退到原始关键字。"""
        result = SearchChain._site_search_keyword(
            site={"language": "en"},
            keyword="Inception",
            mediainfo=None,
            area="title",
            english_keyword=None,
        )
        assert result == "Inception"

    def test_imdbid_area_without_mediainfo(self):
        """imdbid 区域但无媒体信息时，英文站点应回退到英文译名。"""
        result = SearchChain._site_search_keyword(
            site={"language": "en"},
            keyword="Inception",
            mediainfo=None,
            area="imdbid",
            english_keyword="English Title",
        )
        assert result == "English Title"


class TestResolveEnglishKeyword:
    """中文转英文译名逻辑测试。"""

    def test_non_chinese_passthrough(self):
        """非中文关键字应原样返回，不触发 TMDB 查询。"""
        chain = _build_search_chain()
        result = chain._resolve_english_keyword(keyword="Inception", mediainfo=None)
        assert result == "Inception"

    def test_uses_mediainfo_en_title(self):
        """已有媒体信息时应优先使用 en_title。"""
        chain = _build_search_chain()
        media = MediaInfo(title="流浪地球", en_title="The Wandering Earth")
        result = chain._resolve_english_keyword(
            keyword="流浪地球", mediainfo=media, mtype=MediaType.MOVIE
        )
        assert result == "The Wandering Earth"

    def test_uses_mediainfo_original_title(self):
        """en_title 缺失时应回退到 original_title。"""
        chain = _build_search_chain()
        media = MediaInfo(
            title="流浪地球",
            en_title=None,
            original_title="The Wandering Earth",
        )
        result = chain._resolve_english_keyword(
            keyword="流浪地球", mediainfo=media, mtype=MediaType.MOVIE
        )
        assert result == "The Wandering Earth"

    def test_falls_back_to_tmdb_match(self):
        """无媒体信息时应通过 TMDB 按中文标题查询英文译名。"""
        chain = _build_search_chain()
        chain.run_module = Mock(
            return_value={"en_title": "Dune", "original_title": "Dune"}
        )
        result = chain._resolve_english_keyword(
            keyword="沙丘", mediainfo=None, mtype=MediaType.MOVIE
        )
        assert result == "Dune"
        chain.run_module.assert_called_once_with(
            "match_tmdbinfo", name="沙丘", mtype=MediaType.MOVIE
        )

    def test_tmdb_returns_chinese_title_falls_back(self):
        """TMDB 返回的译名仍为中文时应回退到原始关键字。"""
        chain = _build_search_chain()
        chain.run_module = Mock(
            return_value={"en_title": "沙丘", "original_title": "沙丘"}
        )
        result = chain._resolve_english_keyword(
            keyword="沙丘", mediainfo=None, mtype=MediaType.MOVIE
        )
        assert result == "沙丘"

    def test_empty_keyword_returns_none(self):
        """空关键字应返回 None。"""
        chain = _build_search_chain()
        result = chain._resolve_english_keyword(keyword=None, mediainfo=None)
        assert result is None


class TestAsyncResolveEnglishKeyword:
    """异步中文转英文译名逻辑测试。"""

    def test_non_chinese_passthrough(self):
        """非中文关键字应原样返回。"""
        chain = _build_search_chain()
        result = asyncio.run(
            chain._async_resolve_english_keyword(keyword="Inception", mediainfo=None)
        )
        assert result == "Inception"

    def test_uses_mediainfo_en_title(self):
        """已有媒体信息时应优先使用 en_title。"""
        chain = _build_search_chain()
        media = MediaInfo(title="流浪地球", en_title="The Wandering Earth")
        result = asyncio.run(
            chain._async_resolve_english_keyword(
                keyword="流浪地球", mediainfo=media, mtype=MediaType.MOVIE
            )
        )
        assert result == "The Wandering Earth"

    def test_falls_back_to_async_tmdb_match(self):
        """无媒体信息时应通过异步 TMDB 查询英文译名。"""
        chain = _build_search_chain()
        chain.async_run_module = AsyncMock(
            return_value={"en_title": "Dune", "original_title": "Dune"}
        )
        result = asyncio.run(
            chain._async_resolve_english_keyword(
                keyword="沙丘", mediainfo=None, mtype=MediaType.MOVIE
            )
        )
        assert result == "Dune"
        chain.async_run_module.assert_awaited_once()


class TestResolveIndexerSites:
    """索引器列表解析逻辑测试。"""

    def test_no_user_sites_includes_public_indexers(self):
        """无用户站点时公共索引器应被注入。"""
        chain = _build_search_chain()
        chain.run_module = Mock(return_value=IndexerModule.get_public_indexers())
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper, patch(
            "app.chain.search.SitesHelper"
        ) as mock_helper:
            mock_oper.return_value.get.return_value = None  # 公共索引器默认启用
            mock_helper.return_value.get_indexers.return_value = []
            result = chain._resolve_indexer_sites(sites=None)

        assert len(result) == 3
        assert all(idx["public"] is True for idx in result)

    def test_public_indexers_disabled_excludes_them(self):
        """公共索引器开关关闭时不应注入。"""
        chain = _build_search_chain()
        chain.run_module = Mock(return_value=IndexerModule.get_public_indexers())
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper, patch(
            "app.chain.search.SitesHelper"
        ) as mock_helper:
            mock_oper.return_value.get.return_value = False  # 显式关闭
            mock_helper.return_value.get_indexers.return_value = []
            result = chain._resolve_indexer_sites(sites=None)

        assert result == []

    def test_user_sites_merged_with_public(self):
        """用户站点应与公共索引器合并。"""
        user_site = {
            "id": 1,
            "name": "PT站",
            "domain": "https://pt.example.com/",
            "language": "zh",
        }
        chain = _build_search_chain()
        chain.run_module = Mock(return_value=IndexerModule.get_public_indexers())
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper, patch(
            "app.chain.search.SitesHelper"
        ) as mock_helper:
            mock_oper.return_value.get.return_value = None  # 默认启用
            mock_helper.return_value.get_indexers.return_value = [user_site]
            result = chain._resolve_indexer_sites(sites=None)

        assert len(result) == 4
        assert any(idx.get("id") == 1 for idx in result)
        assert sum(1 for idx in result if idx.get("public") is True) == 3


class TestAsyncResolveIndexerSites:
    """异步索引器列表解析逻辑测试。"""

    def test_no_user_sites_includes_public_indexers(self):
        """无用户站点时公共索引器应被注入（异步路径）。"""
        chain = _build_search_chain()
        chain.async_run_module = AsyncMock(
            return_value=IndexerModule.get_public_indexers()
        )
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper, patch(
            "app.chain.search.SitesHelper"
        ) as mock_helper:
            mock_oper.return_value.get.return_value = None
            mock_helper.return_value.async_get_indexers = AsyncMock(return_value=[])
            result = asyncio.run(chain._async_resolve_indexer_sites(sites=None))

        assert len(result) == 3
        assert all(idx["public"] is True for idx in result)

    def test_public_indexers_disabled_excludes_them(self):
        """公共索引器开关关闭时不应注入（异步路径）。"""
        chain = _build_search_chain()
        chain.async_run_module = AsyncMock(
            return_value=IndexerModule.get_public_indexers()
        )
        with patch(
            "app.chain.search.SystemConfigOper"
        ) as mock_oper, patch(
            "app.chain.search.SitesHelper"
        ) as mock_helper:
            mock_oper.return_value.get.return_value = False
            mock_helper.return_value.async_get_indexers = AsyncMock(return_value=[])
            result = asyncio.run(chain._async_resolve_indexer_sites(sites=None))

        assert result == []
