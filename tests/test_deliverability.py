import pytest
import re

from email_validator import EmailUndeliverableError, \
                            validate_email, caching_resolver
from email_validator.deliverability import validate_email_deliverability

from mocked_dns_response import MockedDnsResponseData, MockedDnsResponseDataCleanup  # noqa: F401

RESOLVER = MockedDnsResponseData.create_resolver()


@pytest.mark.parametrize(
    'domain,expected_response',
    [
        ('gmail.com', {'mx': [(5, 'gmail-smtp-in.l.google.com'), (10, 'alt1.gmail-smtp-in.l.google.com'), (20, 'alt2.gmail-smtp-in.l.google.com'), (30, 'alt3.gmail-smtp-in.l.google.com'), (40, 'alt4.gmail-smtp-in.l.google.com')], 'mx_fallback_type': None}),
        ('pages.github.com', {'mx': [(0, 'pages.github.com')], 'mx_fallback_type': 'A'}),
    ],
)
def test_deliverability_found(domain, expected_response):
    response = validate_email_deliverability(domain, domain, dns_resolver=RESOLVER)
    assert response == expected_response


def test_deliverability_fails():
    # Domain does not exist.
    domain = 'xkxufoekjvjfjeodlfmdfjcu.com'
    with pytest.raises(EmailUndeliverableError, match=f'The domain name {domain} does not exist'):
        validate_email_deliverability(domain, domain, dns_resolver=RESOLVER)

    # Null MX record.
    domain = 'example.com'
    with pytest.raises(EmailUndeliverableError, match=f'The domain name {domain} does not accept email'):
        validate_email_deliverability(domain, domain, dns_resolver=RESOLVER)

    # No MX record, A record fallback, reject-all SPF record.
    domain = 'nellis.af.mil'
    with pytest.raises(EmailUndeliverableError, match=f'The domain name {domain} does not send email'):
        validate_email_deliverability(domain, domain, dns_resolver=RESOLVER)

    # No MX or A/AAAA records, but some other DNS records must
    # exist such that the response is NOANSWER instead of NXDOMAIN.
    domain = 'justtxt.joshdata.me'
    with pytest.raises(EmailUndeliverableError, match=f'The domain name {domain} does not accept email'):
        validate_email_deliverability(domain, domain, dns_resolver=RESOLVER)


@pytest.mark.parametrize(
    'email_input',
    [
        ('me@mail.example'),
        ('me@example.com'),
        ('me@mail.example.com'),
    ],
)
def test_email_example_reserved_domain(email_input):
    # Since these all fail deliverabiltiy from a static list,
    # DNS deliverability checks do not arise.
    with pytest.raises(EmailUndeliverableError) as exc_info:
        validate_email(email_input, dns_resolver=RESOLVER)
    # print(f'({email_input!r}, {str(exc_info.value)!r}),')
    assert re.match(r"The domain name [a-z\.]+ does not (accept email|exist)\.", str(exc_info.value)) is not None


def test_deliverability_dns_timeout():
    response = validate_email_deliverability('timeout.com', 'timeout.com', dns_resolver=RESOLVER)
    assert "mx" not in response
    assert response.get("unknown-deliverability") == "timeout"


@pytest.mark.network
def test_caching_dns_resolver():
    class TestCache:
        def __init__(self):
            self.cache = {}

        def get(self, key):
            return self.cache.get(key)

        def put(self, key, value):
            self.cache[key] = value

    cache = TestCache()
    resolver = caching_resolver(timeout=1, cache=cache)
    validate_email("test@gmail.com", dns_resolver=resolver)
    assert len(cache.cache) == 1

    validate_email("test@gmail.com", dns_resolver=resolver)
    assert len(cache.cache) == 1
