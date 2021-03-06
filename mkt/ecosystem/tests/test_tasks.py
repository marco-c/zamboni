import mock
from nose.tools import eq_

from django.http import Http404

import amo.tests
from mkt.ecosystem.models import MdnCache
from mkt.ecosystem.tasks import _fetch_mdn_page, _update_mdn_items


test_items = [
    {
        'title': 'Test Mdn Page',
        'name': 'test',
        'local': 'en',
        'mdn': 'https://developer.mozilla.org/%(locale)s/HTML/HTML5'
    }
]


def fake_page(url):
    return """<section id='article-nav'>
                    <div class='page-toc'>
                        <ol>
                            <li><script>alert('xss');</script></li>
                        </ol>
                    </div>
                </section>
                <section id='pageText'>
                    <b>hi</b><script>alert('xss');</script>
                </section>"""


def raise_exception(url):
    raise Exception('test')


def raise_404(url):
    raise Http404


class TestMdnCacheUpdate(amo.tests.TestCase):
    fixtures = ['ecosystem/mdncache-item']

    def setUp(self):
        for item in test_items:
            item['url'] = item['mdn'] % {'locale': 'en'}

    @mock.patch('mkt.ecosystem.tasks._get_page', new=fake_page)
    def test_get_page_content(self):
        content = _fetch_mdn_page(test_items[0]['url'])
        eq_(2, len(content))

    @mock.patch('mkt.ecosystem.tasks._get_page', new=fake_page)
    def test_refresh_mdn_cache(self):
        _update_mdn_items(test_items)
        eq_('test', MdnCache.objects.get(name=test_items[0]['name'],
                                         locale='en').name)

    @mock.patch('mkt.ecosystem.tasks._get_page', new=fake_page)
    def test_refresh_mdn_cache_with_old_data(self):
        eq_('old', MdnCache.objects.get(name='old',
                                        locale='en').name)
        _update_mdn_items(test_items)
        eq_('test', MdnCache.objects.get(name=test_items[0]['name'],
                                         locale='en').name)
        eq_(1, MdnCache.objects.count())

        with self.assertRaises(MdnCache.DoesNotExist):
            MdnCache.objects.get(name='old', locale='en')

    @mock.patch('mkt.ecosystem.tasks._get_page', new=fake_page)
    def test_ensure_content_xss_safe(self):
        content = _fetch_mdn_page(test_items[0]['url'])
        assert '<script>' not in content[1]
        assert '&lt;script&gt;alert' in content[1]
        assert '<b>hi</b>' in content[1]

    @mock.patch('mkt.ecosystem.tasks._get_page', new=fake_page)
    def test_ensure_toc_xss_safe(self):
        content = _fetch_mdn_page(test_items[0]['url'])
        assert '<script>' not in content[0]
        assert '&lt;script&gt;alert' in content[0]
        assert '<li>' in content[0]

    @mock.patch('mkt.ecosystem.tasks._get_page', new=raise_exception)
    def test_dont_delete_on_exception(self):
        with self.assertRaises(Exception):
            _update_mdn_items(test_items)
            eq_(2, MdnCache.objects.count())

    @mock.patch('mkt.ecosystem.tasks._get_page', new=raise_404)
    def test_continue_on_404_exception(self):
        _update_mdn_items(test_items)
        eq_(0, MdnCache.objects.count())
