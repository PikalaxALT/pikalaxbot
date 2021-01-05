import aiohttp

__all__ = ('mystbin', 'hastebin')


async def do_bin(domain: str, content: str, cs: aiohttp.ClientSession = None):
    if close_after := cs is None:
        cs = aiohttp.ClientSession(raise_for_status=True)
    timeout = aiohttp.ClientTimeout(total=15.0)
    async with cs.post('{}/documents'.format(domain), data=content.encode('utf-8'), timeout=timeout) as res:
        post = await res.json()
    if close_after:
        await cs.close()
    return '{0}/{key}'.format(domain, **post)


def hastebin(content: str, cs: aiohttp.ClientSession = None):
    """Upload the content to hastebin and return the url.

    :param content: str: Raw content to upload
    :param cs: `aiohttp.ClientSession`: Optional ClientSession instance
    :return: str: URL to the uploaded content
    :raises aiohttp.ClientException: on failure to upload
    """
    return do_bin('https://hastebin.com', content, cs=cs)


def mystbin(content: str, cs: aiohttp.ClientSession = None):
    """Upload the content to mystbin and return the url.

    :param content: str: Raw content to upload
    :param cs: `aiohttp.ClientSession`: Optional ClientSession instance
    :return: str: URL to the uploaded content
    :raises aiohttp.ClientException: on failure to upload
    """
    return do_bin('https://mystb.in', content, cs=cs)
