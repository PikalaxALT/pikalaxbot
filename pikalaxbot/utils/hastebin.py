import aiohttp

__all__ = ('hastebin',)


async def hastebin(content: str) -> str:
    """Upload the content to hastebin and return the url.

    :param content: str: Raw content to upload
    :return: str: URL to the uploaded content
    :raises aiohttp.ClientException: on failure to upload
    """
    timeout = aiohttp.ClientTimeout(total=15.0)
    async with aiohttp.ClientSession(raise_for_status=True) as cs:
        async with cs.post('https://hastebin.com/documents', data=content.encode('utf-8'), timeout=timeout) as res:
            post = await res.json()
    uri = post['key']
    return f'https://hastebin.com/{uri}'
