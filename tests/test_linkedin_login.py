# -*- coding: utf-8 -*-
"""
    test_linkedin_auth

    Test the linkedin login

    :copyright: (c) 2012-2013 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details.
"""
import os
import unittest
import BaseHTTPServer
import urlparse
import threading
import webbrowser
from StringIO import StringIO

from lxml import etree

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT, \
    test_view, test_depends
from trytond.transaction import Transaction
from nereid.testing import NereidTestCase

from trytond.pool import Pool

_def = []
def get_from_env(key):
    """
    Find a value from environ or return the default if specified
    If the return value is not specified then raise an error if
    the value is NOT in the environment
    """
    try:
        return os.environ[key]
    except KeyError, error:
        raise Exception("%s is not set in environ" % key)

REQUEST_RECEIVED = None


class RequestStack(threading.local):
    "Stack for storing the responses from async server"
    items = []

_request_ctx_stack = RequestStack()


class LinkedInHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    "Special Class to handle the POST from LinkedIn"

    def do_GET(self):
        "Handle POST"
        parsed_path = urlparse.urlparse(self.path)
        print "parsed_path", parsed_path
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            "Hola, go back to your terminal window to see results"
        )
        return


class TestLinkedInAuth(NereidTestCase):
    "Test LinkedIn Authenticated login"

    def setUp(self):
        "Setup"
        trytond.tests.test_tryton.install_module('nereid_auth_linkedin')

        self.Country = Pool().get('country.country')
        self.Currency = Pool().get('currency.currency')
        self.NereidUser = Pool().get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.Website = POOL.get('nereid.website')

    def setup_defaults(self):
        "Setup defaults"

        usd = self.Currency.create({
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        })
        self.company = self.Country.create({
            'name': 'Openlabs',
            'currency': usd.id
        })
        self.guest_user = self.NereidUser.create({
            'name': 'Guest User',
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        })
        self.registered_user = self.NereidUser.create({
            'name': 'Registered User',
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
        })
        url_map, = self.UrlMap.search([], limit=1)
        en_us, = self.Language.search([('code', '=', 'en_US')])
        self.site = self.nereid_website_obj.create({
            'name': 'localhost',
            'url_map': url_map.id,
            'company': self.company.id,
            'application_user': USER,
            'default_language': en_us.id,
            'guest_user': self.guest_user.id,
        })

    def get_template_source(self, name):
        """
        Return templates
        """
        self.templates = {
            'localhost/home.jinja': '{{ get_flashed_messages() }}',
            'localhost/login.jinja':
                '{{ login_form.errors }} {{ get_flashed_messages() }}'
        }
        return self.templates.get(name)

    def test_0005_test_view(self):
        """
        Test the view
        """
        test_view('nereid_auth_linkedin')

    def test_0006_test_depends(self):
        """
        Test Depends
        """
        test_depends()

    def test_0010_login(self):
        """
        Check for login with the next argument without API settings
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                response = c.get('/en_US/auth/linkedin?next=/en_US')
                self.assertEqual(response.status_code, 302)

                # Redirect to the home page since
                self.assertTrue(
                    '<a href="/en_US/login">/en_US/login</a>' in response.data
                )
                response = c.get('/')
                self.assertTrue(
                    'LinkedIn login is not available at the moment' \
                    in response.data
                )

    def test_0020_login(self):
        """
        Login with linkedin settings
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            self.Website.write([self.site], {
                'facebook_app_id': get_from_env('LINKEDIN_API_KEY'),
                'facebook_app_secret': get_from_env('LINKEDIN_API_SECRET'),
            })

            with app.test_client() as c:
                response = c.get('/en_US/auth/linkedin?next=/en_US')
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    'https://api.linkedin.com/uas/oauth/authenticate' in \
                    response.data
                )

                # send the user to the webbrowser and wait for a redirect
                parser = etree.HTMLParser()
                tree   = etree.parse(StringIO(response.data), parser)
                webbrowser.open(tree.xpath('//p/a')[0].values()[0])


def suite():
    "Nereid test suite"
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestLinkedInAuth)
    )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
