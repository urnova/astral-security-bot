
import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import json

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

class SecurityBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
    
    async def on_ready(self):
        print(f'{self.user} est connecté et prêt!')
        print(f'Bot ID: {self.user.id}')
        try:
            synced = await self.tree.sync()
            print(f'Synchronisé {len(synced)} commandes slash')
        except Exception as e:
            print(f'Erreur lors de la synchronisation: {e}')
        print('-------------------')

bot = SecurityBot()

# Variables globales
LOG_CHANNEL_ID = None
logs_data = []
MAINTENANCE_MODE = False
MAINTENANCE_REASON = ""

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
    
    if len(logs_data) > 1000:
        logs_data.pop(0)
    
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

# Commandes slash pour la modération
@bot.tree.command(name="kick", description="Exclure un membre du serveur")
@app_commands.describe(
    member="Le membre à exclure",
    reason="La raison de l'exclusion"
)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    if MAINTENANCE_MODE and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="🔧 Serveur en maintenance",
            description=f"Le serveur est actuellement en maintenance.\n**Raison:** {MAINTENANCE_REASON}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        await member.kick(reason=reason)
        
        embed = discord.Embed(
            title="👢 Membre exclu",
            description=f"{member.mention} a été exclu du serveur",
            color=discord.Color.orange()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action("kick", interaction.user, member, reason)
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour exclure ce membre.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'exclusion: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="Bannir un membre du serveur")
@app_commands.describe(
    member="Le membre à bannir",
    reason="La raison du bannissement"
)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    try:
        await member.ban(reason=reason)
        
        embed = discord.Embed(
            title="🔨 Membre banni",
            description=f"{member.mention} a été banni du serveur",
            color=discord.Color.red()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action("ban", interaction.user, member, reason)
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour bannir ce membre.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du bannissement: {str(e)}", ephemeral=True)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
@app_commands.describe(
    user_id="L'ID de l'utilisateur à débannir",
    reason="La raison du débannissement"
)
async def unban_slash(interaction: discord.Interaction, user_id: str, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    try:
        user_id_int = int(user_id)
        user = await bot.fetch_user(user_id_int)
        await interaction.guild.unban(user, reason=reason)
        
        embed = discord.Embed(
            title="✅ Utilisateur débanni",
            description=f"{user.mention} a été débanni du serveur",
            color=discord.Color.green()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action("unban", interaction.user, user, reason)
        
    except ValueError:
        await interaction.response.send_message("❌ ID utilisateur invalide.", ephemeral=True)
    except discord.NotFound:
        await interaction.response.send_message("❌ Utilisateur non trouvé ou non banni.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du débannissement: {str(e)}", ephemeral=True)

@bot.tree.command(name="mute", description="Mettre un membre en timeout")
@app_commands.describe(
    member="Le membre à mettre en timeout",
    duration="Durée en minutes (défaut: 10)",
    reason="La raison du timeout"
)
async def mute_slash(interaction: discord.Interaction, member: discord.Member, duration: int = 10, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    try:
        timeout_until = datetime.now() + timedelta(minutes=duration)
        await member.timeout(timeout_until, reason=reason)
        
        embed = discord.Embed(
            title="🔇 Membre mis en timeout",
            description=f"{member.mention} a été mis en timeout pour {duration} minutes",
            color=discord.Color.orange()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action("mute", interaction.user, member, f"{reason} ({duration} min)")
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour timeout ce membre.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du timeout: {str(e)}", ephemeral=True)

@bot.tree.command(name="unmute", description="Retirer le timeout d'un membre")
@app_commands.describe(
    member="Le membre dont retirer le timeout",
    reason="La raison du retrait de timeout"
)
async def unmute_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    try:
        await member.timeout(None, reason=reason)
        
        embed = discord.Embed(
            title="🔊 Timeout retiré",
            description=f"Le timeout de {member.mention} a été retiré",
            color=discord.Color.green()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action("unmute", interaction.user, member, reason)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du retrait du timeout: {str(e)}", ephemeral=True)

@bot.tree.command(name="warn", description="Avertir un membre")
@app_commands.describe(
    member="Le membre à avertir",
    reason="La raison de l'avertissement"
)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison spécifiée"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚠️ Avertissement",
        description=f"{member.mention} a reçu un avertissement",
        color=discord.Color.yellow()
    )
    embed.add_field(name="Raison", value=reason, inline=False)
    embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
    
    await interaction.response.send_message(embed=embed)
    await log_action("warn", interaction.user, member, reason)

@bot.tree.command(name="clear", description="Supprimer des messages")
@app_commands.describe(
    amount="Nombre de messages à supprimer (max 100)"
)
async def clear_slash(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    if amount > 100:
        amount = 100
    
    try:
        await interaction.response.defer()
        deleted = await interaction.channel.purge(limit=amount)
        
        embed = discord.Embed(
            title="🧹 Messages supprimés",
            description=f"{len(deleted)} messages ont été supprimés",
            color=discord.Color.blue()
        )
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Canal", value=interaction.channel.mention, inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        await log_action("clear", interaction.user, channel=interaction.channel, reason=f"{len(deleted)} messages supprimés")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la suppression: {str(e)}", ephemeral=True)

@bot.tree.command(name="logs", description="Afficher les logs de modération")
@app_commands.describe(
    limit="Nombre de logs à afficher (max 20)"
)
async def logs_slash(interaction: discord.Interaction, limit: int = 10):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    if not logs_data:
        await interaction.response.send_message("❌ Aucun log disponible.", ephemeral=True)
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
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setlogs", description="Configurer le canal de logs")
@app_commands.describe(
    channel="Le canal où envoyer les logs"
)
async def setlogs_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    
    embed = discord.Embed(
        title="✅ Canal de logs configuré",
        description=f"Les logs seront maintenant envoyés dans {channel.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
    await log_action("Configuration", interaction.user, channel=channel)

@bot.tree.command(name="maintenance", description="Activer le mode maintenance")
@app_commands.describe(
    reason="Raison de la maintenance"
)
async def maintenance_slash(interaction: discord.Interaction, reason: str = "Maintenance en cours"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    global MAINTENANCE_MODE, MAINTENANCE_REASON
    MAINTENANCE_MODE = True
    MAINTENANCE_REASON = reason
    
    embed = discord.Embed(
        title="🔧 Mode maintenance activé",
        description=f"Le serveur est maintenant en mode maintenance.\n**Raison:** {reason}",
        color=discord.Color.orange()
    )
    embed.add_field(name="Activé par", value=interaction.user.mention, inline=True)
    
    await interaction.response.send_message(embed=embed)
    
    for channel in interaction.guild.text_channels:
        try:
            if channel.permissions_for(interaction.guild.me).send_messages and channel != interaction.channel:
                await channel.send(embed=embed)
        except:
            continue
    
    await log_action("maintenance_enable", interaction.user, reason=reason)

@bot.tree.command(name="maintenance_off", description="Désactiver le mode maintenance")
async def maintenance_off_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cette commande est réservée aux administrateurs.", ephemeral=True)
        return
    
    global MAINTENANCE_MODE, MAINTENANCE_REASON
    MAINTENANCE_MODE = False
    old_reason = MAINTENANCE_REASON
    MAINTENANCE_REASON = ""
    
    embed = discord.Embed(
        title="✅ Mode maintenance désactivé",
        description="Le serveur est de nouveau opérationnel!",
        color=discord.Color.green()
    )
    embed.add_field(name="Désactivé par", value=interaction.user.mention, inline=True)
    
    await interaction.response.send_message(embed=embed)
    
    for channel in interaction.guild.text_channels:
        try:
            if channel.permissions_for(interaction.guild.me).send_messages and channel != interaction.channel:
                await channel.send(embed=embed)
        except:
            continue
    
    await log_action("maintenance_disable", interaction.user, reason=f"Fin de: {old_reason}")

@bot.tree.command(name="serverinfo", description="Afficher les informations du serveur")
async def serverinfo_slash(interaction: discord.Interaction):
    guild = interaction.guild
    
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
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="commands", description="Afficher toutes les commandes disponibles")
async def commands_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Commandes du Bot de Sécurité",
        description="Voici toutes les commandes disponibles:",
        color=discord.Color.blue()
    )
    
    if interaction.user.guild_permissions.administrator:
        moderation_commands = [
            ("/kick", "Exclure un membre du serveur"),
            ("/ban", "Bannir un membre du serveur"),
            ("/unban", "Débannir un utilisateur"),
            ("/mute", "Mettre un membre en timeout"),
            ("/unmute", "Retirer le timeout d'un membre"),
            ("/warn", "Avertir un membre"),
            ("/clear", "Supprimer des messages")
        ]
        
        system_commands = [
            ("/logs", "Voir les logs de modération"),
            ("/setlogs", "Configurer le canal de logs"),
            ("/maintenance", "Activer le mode maintenance"),
            ("/maintenance_off", "Désactiver le mode maintenance"),
            ("/commands", "Afficher cette liste")
        ]
        
        embed.add_field(name="🔨 Modération (Admin seulement)", value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in moderation_commands]), inline=False)
        embed.add_field(name="⚙️ Système (Admin seulement)", value="\n".join([f"`{cmd}` - {desc}" for cmd, desc in system_commands]), inline=False)
        embed.add_field(name="📊 Public", value="`/serverinfo` - Informations du serveur", inline=False)
        embed.set_footer(text="Tapez / dans Discord pour voir toutes les commandes disponibles avec l'autocomplétion!")
    else:
        embed.add_field(
            name="Commandes disponibles",
            value="`/serverinfo` - Voir les informations du serveur\n`/commands` - Afficher cette aide",
            inline=False
        )
        embed.add_field(
            name="Note",
            value="Les commandes de modération sont réservées aux administrateurs du serveur.",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Événement pour bloquer les messages pendant la maintenance
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if MAINTENANCE_MODE and not message.author.guild_permissions.administrator:
        if not message.content.startswith(bot.command_prefix):
            try:
                await message.delete()
                embed = discord.Embed(
                    title="🔧 Serveur en maintenance",
                    description=f"Votre message a été supprimé car le serveur est en maintenance.\n**Raison:** {MAINTENANCE_REASON}",
                    color=discord.Color.orange()
                )
                await message.author.send(embed=embed)
            except:
                pass
        return
    
    await bot.process_commands(message)

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
