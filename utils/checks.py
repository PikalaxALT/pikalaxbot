

def markov_general_checks(ctx):
    if not ctx.bot.initialized:
        return False
    if ctx.channel.id not in ctx.bot.whitelist:
        return False
    if ctx.author.bot:
        return False
    if len(ctx.bot.markov_channels) == 0:
        return False
    if ctx.author == ctx.bot.user:
        return False
    if ctx.command is not None:
        return False
    return True


def can_markov(ctx):
    if not markov_general_checks(ctx):
        return False
    if ctx.bot.user.mentioned_in(ctx.message):
        return True
    words = ctx.message.clean_content.lower().split()
    if ctx.bot.user.name.lower() in words:
        return True
    if ctx.bot.get_nick(ctx.guild).lower() in words:
        return True
    return False


def can_learn_markov(ctx, force=False):
    if not (force or markov_general_checks(ctx)):
        return False
    if ctx.author.bot:
        return False
    return ctx.channel.id in ctx.bot.markov_channels and not ctx.message.clean_content.startswith('!')
