
import os
import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import json

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Canal de logs (à configurer via commande)
LOG_CHANNEL_ID = None
logs_data = []

# Événement de démarrage
@bot.event
async def on_ready():
    print(f'{bot.user} est connecté et prêt!')
    print(f'Bot ID: {bot.user.id}')
    print('-------------------')

# Système de logs
async def log_action(action, user, target=None, reason=None, channel=None):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'user': str(user),
        'target': str(target) if target else None,
        'reason': reason,
        'channel': str(channel) if channel else None
    }
    logs_data.append(log_entry)
    
    # Limiter à 1000 logs maximum
    if len(logs_data) > 1000:
        logs_data.pop(0)
    
    # Envoyer dans le canal de logs si configuré
    if LOG_CHANNEL_ID:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title=f"🔒 Action de modération: {action}",
                color=discord.Color.red() if action in ['kick', 'ban'] else discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Modérateur", value=user, inline=True)
            if target:
                embed.add_field(name="Cible", value=target, inline=True)
            if reason:
                embed.add_field(name="Raison", value=reason, inline=False)
            if channel:
                embed.add_field(name="Canal", value=channel, inline=True)
            
            await log_channel.send(embed=embed)

# Configuration du canal de logs
@bot.command(name='setlogs')
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel):
    """Configure le canal pour les logs de modération"""
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    
    embed = discord.Embed(
        title="✅ Canal de logs configuré",
        description=f"Les logs seront maintenant envoyés dans {channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    await log_action("Configuration", ctx.author, channel=channel)

# Commande kick
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, reason="Aucune raison spécifiée"):
    """Exclure un membre du serveur"""
    try:
        await member.kick(reason=reason)
        
        embed = discord.Embed(
            title="👢 Membre exclu",
            description=f"{member.mention} a été exclu du serveur",
            color=discord.Color.orange()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        await log_action("kick", ctx.author, member, reason)
        
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour exclure ce membre.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de l'exclusion: {str(e)}")

# Commande ban
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_member(ctx, member: discord.Member, *, reason="Aucune raison spécifiée"):
    """Bannir un membre du serveur"""
    try:
        await member.ban(reason=reason)
        
        embed = discord.Embed(
            title="🔨 Membre banni",
            description=f"{member.mention} a été banni du serveur",
            color=discord.Color.red()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        await log_action("ban", ctx.author, member, reason)
        
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour bannir ce membre.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du bannissement: {str(e)}")

# Commande unban
@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban_member(ctx, user_id: int, *, reason="Aucune raison spécifiée"):
    """Débannir un utilisateur"""
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        
        embed = discord.Embed(
            title="✅ Utilisateur débanni",
            description=f"{user.mention} a été débanni du serveur",
            color=discord.Color.green()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        await log_action("unban", ctx.author, user, reason)
        
    except discord.NotFound:
        await ctx.send("❌ Utilisateur non trouvé ou non banni.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du débannissement: {str(e)}")

# Commande mute (timeout)
@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute_member(ctx, member: discord.Member, duration: int = 10, *, reason="Aucune raison spécifiée"):
    """Mettre un membre en timeout (durée en minutes)"""
    try:
        timeout_until = datetime.now() + timedelta(minutes=duration)
        await member.timeout(timeout_until, reason=reason)
        
        embed = discord.Embed(
            title="🔇 Membre mis en timeout",
            description=f"{member.mention} a été mis en timeout pour {duration} minutes",
            color=discord.Color.orange()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        await log_action("mute", ctx.author, member, f"{reason} ({duration} min)")
        
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour timeout ce membre.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du timeout: {str(e)}")

# Commande unmute
@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute_member(ctx, member: discord.Member, *, reason="Aucune raison spécifiée"):
    """Retirer le timeout d'un membre"""
    try:
        await member.timeout(None, reason=reason)
        
        embed = discord.Embed(
            title="🔊 Timeout retiré",
            description=f"Le timeout de {member.mention} a été retiré",
            color=discord.Color.green()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        await log_action("unmute", ctx.author, member, reason)
        
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du retrait du timeout: {str(e)}")

# Commande clear (supprimer messages)
@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    """Supprimer un nombre de messages (max 100)"""
    if amount > 100:
        amount = 100
    
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 pour inclure la commande
        
        embed = discord.Embed(
            title="🧹 Messages supprimés",
            description=f"{len(deleted) - 1} messages ont été supprimés",
            color=discord.Color.blue()
        )
        embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
        embed.add_field(name="Canal", value=ctx.channel.mention, inline=True)
        
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await msg.delete()
        
        await log_action("clear", ctx.author, channel=ctx.channel, reason=f"{len(deleted) - 1} messages supprimés")
        
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la suppression: {str(e)}")

# Commande pour voir les logs
@bot.command(name='logs')
@commands.has_permissions(view_audit_log=True)
async def view_logs(ctx, limit: int = 10):
    """Afficher les derniers logs de modération"""
    if not logs_data:
        await ctx.send("❌ Aucun log disponible.")
        return
    
    if limit > 20:
        limit = 20
    
    recent_logs = logs_data[-limit:]
    
    embed = discord.Embed(
        title="📋 Logs de modération",
        description=f"Affichage des {len(recent_logs)} derniers logs",
        color=discord.Color.blue()
    )
    
    for log in reversed(recent_logs):
        log_text = f"**{log['action']}** par {log['user']}"
        if log['target']:
            log_text += f" → {log['target']}"
        if log['reason']:
            log_text += f"\n*Raison: {log['reason']}*"
        if log['channel']:
            log_text += f"\n*Canal: {log['channel']}*"
        
        embed.add_field(
            name=f"⏰ {log['timestamp']}",
            value=log_text,
            inline=False
        )
    
    await ctx.send(embed=embed)

# Commande warn
@bot.command(name='warn')
@commands.has_permissions(kick_members=True)
async def warn_member(ctx, member: discord.Member, *, reason="Aucune raison spécifiée"):
    """Avertir un membre"""
    embed = discord.Embed(
        title="⚠️ Avertissement",
        description=f"{member.mention} a reçu un avertissement",
        color=discord.Color.yellow()
    )
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
    
    await ctx.send(embed=embed)
    await log_action("warn", ctx.author, member, reason)

# Commande info serveur
@bot.command(name='serverinfo')
async def server_info(ctx):
    """Afficher les informations du serveur"""
    guild = ctx.guild
    
    embed = discord.Embed(
        title=f"📊 Informations - {guild.name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Propriétaire", value=guild.owner.mention, inline=True)
    embed.add_field(name="Membres", value=guild.member_count, inline=True)
    embed.add_field(name="Canaux", value=len(guild.channels), inline=True)
    embed.add_field(name="Rôles", value=len(guild.roles), inline=True)
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    
    await ctx.send(embed=embed)

# Commande d'aide
@bot.command(name='help_security')
async def help_security(ctx):
    """Afficher toutes les commandes de sécurité disponibles"""
    embed = discord.Embed(
        title="🛡️ Commandes de sécurité",
        description="Voici toutes les commandes disponibles:",
        color=discord.Color.blue()
    )
    
    commands_list = [
        ("!kick <@membre> [raison]", "Exclure un membre"),
        ("!ban <@membre> [raison]", "Bannir un membre"),
        ("!unban <user_id> [raison]", "Débannir un utilisateur"),
        ("!mute <@membre> [minutes] [raison]", "Mettre en timeout"),
        ("!unmute <@membre> [raison]", "Retirer le timeout"),
        ("!clear [nombre]", "Supprimer des messages"),
        ("!warn <@membre> [raison]", "Avertir un membre"),
        ("!logs [nombre]", "Voir les logs de modération"),
        ("!setlogs #canal", "Configurer le canal de logs"),
        ("!serverinfo", "Informations du serveur")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    await ctx.send(embed=embed)

# Gestion des erreurs
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour cette commande.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre non trouvé.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argument invalide. Utilisez `!help_security` pour voir la syntaxe.")
    else:
        await ctx.send(f"❌ Une erreur s'est produite: {str(error)}")

# Événements de modération automatique
@bot.event
async def on_member_join(member):
    await log_action("member_join", "Système", member)

@bot.event
async def on_member_remove(member):
    await log_action("member_leave", "Système", member)

# Démarrage du bot
try:
    token = os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("Veuillez ajouter votre token dans les Secrets avec la clé TOKEN.")
    bot.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print("Trop de requêtes envoyées aux serveurs Discord")
        print("Consultez: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e
