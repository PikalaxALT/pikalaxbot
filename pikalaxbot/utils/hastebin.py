import aiohttp

__all__ = ('mystbin', 'hastebin')


async def hastebin(content: str, **kwargs) -> str:
    """Upload the content to hastebin and return the url.

    :param content: str: Raw content to upload
    :param cs: `aiohttp.ClientSession`: Optional ClientSession instance
    :return: str: URL to the uploaded content
    :raises aiohttp.ClientException: on failure to upload
    """
    cs = kwargs.get('cs') or aiohttp.ClientSession(raise_for_status=True)
    timeout = aiohttp.ClientTimeout(total=15.0)
    async with cs.post('https://hastebin.com/documents', data=content.encode('utf-8'), timeout=timeout) as res:
        post = await res.json()
    uri = post['key']
    if 'cs' not in kwargs:
        await cs.close()
    return f'https://hastebin.com/{uri}'


async def mystbin(content: str, **kwargs) -> str:
    """Upload the content to mystbin and return the url.

    :param content: str: Raw content to upload
    :param cs: `aiohttp.ClientSession`: Optional ClientSession instance
    :return: str: URL to the uploaded content
    :raises aiohttp.ClientException: on failure to upload
    """
    cs = kwargs.get('cs') or aiohttp.ClientSession(raise_for_status=True)
    timeout = aiohttp.ClientTimeout(total=15.0)
    async with cs.post('https://mystb.in/documents', data=content.encode('utf-8'), timeout=timeout) as res:
        post = await res.json()
    uri = post['key']
    if 'cs' not in kwargs:
        await cs.close()
    return f'https://mystb.in/{uri}'
