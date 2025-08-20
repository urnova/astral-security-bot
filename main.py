
import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio
import logging
from dotenv import load_dotenv

# Configuration
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Crée le groupe de commandes 'admin' avec les permissions d'administrateur
admin_group = app_commands.Group(
    name="admin",
    description="Commandes réservées aux administrateurs",
    default_permissions=discord.Permissions(administrator=True)
)
bot.tree.add_command(admin_group)

# Variables globales pour le cache
SERVER_DATA = {}

def get_data_file(guild_id):
    """Retourne le chemin du fichier de données pour un serveur"""
    return f"configs/server_{guild_id}.json"

def load_server_data(guild_id):
    """Charge les données d'un serveur depuis le fichier JSON"""
    file_path = get_data_file(guild_id)
    default_data = {
        "log_channel_id": None,
        "maintenance_mode": False,
        "maintenance_reason": "",
        "anti_spam": {},
        "warns": {},
        "automod_enabled": True,
        "raid_protection": True,
        "banned_words": ["spam", "hack", "scam"],
        "max_mentions": 5,
        "max_messages_per_minute": 10
    }
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Mettre à jour avec les nouvelles clés si nécessaire
                for key, value in default_data.items():
                    if key not in data:
                        data[key] = value
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    return default_data

def save_server_data(guild_id, data):
    """Sauvegarde les données d'un serveur dans le fichier JSON"""
    file_path = get_data_file(guild_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logging.error(f"Erreur sauvegarde serveur {guild_id}: {e}")

def get_server_data(guild_id):
    """Récupère les données d'un serveur (cache ou fichier)"""
    if guild_id not in SERVER_DATA:
        SERVER_DATA[guild_id] = load_server_data(guild_id)
    return SERVER_DATA[guild_id]

def update_server_data(guild_id, key, value):
    """Met à jour une donnée spécifique d'un serveur"""
    data = get_server_data(guild_id)
    data[key] = value
    save_server_data(guild_id, data)

async def log_action(guild, action_type, user, target=None, reason=None, details=None):
    """Système de logs avancé pour toutes les actions de sécurité"""
    guild_id = guild.id
    data = get_server_data(guild_id)
    log_channel_id = data.get("log_channel_id")
    
    if not log_channel_id:
        return
    
    log_channel = bot.get_channel(log_channel_id)
    if not log_channel:
        return
    
    # Couleurs selon le type d'action
    colors = {
        "kick": 0xff6b6b,
        "ban": 0xff0000,
        "unban": 0x00ff00,
        "warn": 0xffff00,
        "unwarn": 0x00ff00,
        "timeout": 0xffa500,
        "lockdown": 0xff0000,
        "unlock": 0x00ff00,
        "maintenance": 0xffa500,
        "nuke": 0xff4500,
        "automod": 0x9932cc,
        "antiraid": 0x0099ff,
        "message_delete": 0xff6b6b,
        "spam_detected": 0xff0000,
        "member_join": 0x00ff00,
        "member_leave": 0xffa500,
        "security": 0xff0000
    }
    
    # Émojis selon le type
    emojis = {
        "kick": "👢",
        "ban": "🔨",
        "unban": "✅",
        "warn": "⚠️",
        "unwarn": "✅",
        "timeout": "🔇",
        "lockdown": "🚨",
        "unlock": "🎉",
        "maintenance": "🚧",
        "nuke": "💥",
        "automod": "🤖",
        "antiraid": "🛡️",
        "message_delete": "🗑️",
        "spam_detected": "🚫",
        "member_join": "👋",
        "member_leave": "👋",
        "security": "🔒"
    }
    
    embed = discord.Embed(
        title=f"{emojis.get(action_type, '📝')} LOG DE SÉCURITÉ",
        color=colors.get(action_type, 0x0099ff),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Action", value=action_type.upper(), inline=True)
    embed.add_field(name="Modérateur", value=user.mention, inline=True)
    embed.add_field(name="Heure", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
    
    if target:
        embed.add_field(name="Cible", value=target.mention if hasattr(target, 'mention') else str(target), inline=True)
    
    if reason:
        embed.add_field(name="Raison", value=reason, inline=False)
    
    if details:
        embed.add_field(name="Détails", value=details, inline=False)
    
    embed.set_footer(text=f"ID: {user.id} | Serveur: {guild.name}")
    embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
    
    try:
        await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Erreur envoi log: {e}")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} est connecté!')
    print(f'🌐 Connecté à {len(bot.guilds)} serveur(s)')
    
    # Synchronisation globale et par serveur
    try:
        # Sync global
        global_synced = await bot.tree.sync()
        print(f'✅ {len(global_synced)} commandes globales synchronisées')
        
        # Sync par serveur pour les commandes admin
        total_server_synced = 0
        for guild in bot.guilds:
            try:
                server_synced = await bot.tree.sync(guild=guild)
                total_server_synced += len(server_synced)
                print(f'✅ {len(server_synced)} commandes admin sync sur {guild.name}')
            except Exception as e:
                print(f'⚠️ Erreur sync {guild.name}: {e}')
        
        print(f'🎯 TOTAL: {len(global_synced)} globales + {total_server_synced} serveur = {len(global_synced) + total_server_synced} commandes')
        print('🚀 Bot prêt et opérationnel!')
        
    except Exception as e:
        print(f'❌ Erreur critique sync: {e}')
        logging.error(f'Erreur synchronisation: {e}')

# COMMANDES DE MODÉRATION BASIQUES
@admin_group.command(name="kick", description="Exclure un membre")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Membre exclu", description=f"{member.mention} exclu", color=0xff6b6b)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "kick", interaction.user, member, reason)
    except Exception as e:
        await interaction.response.send_message("❌ Erreur lors de l'exclusion", ephemeral=True)
        await log_action(interaction.guild, "security", interaction.user, member, f"Erreur kick: {str(e)}")

@admin_group.command(name="ban", description="Bannir un membre")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Membre banni", description=f"{member.mention} banni", color=0xff0000)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "ban", interaction.user, member, reason)
    except Exception as e:
        await interaction.response.send_message("❌ Erreur lors du ban", ephemeral=True)
        await log_action(interaction.guild, "security", interaction.user, member, f"Erreur ban: {str(e)}")

@admin_group.command(name="unban", description="Débannir un utilisateur")
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "Aucune raison"):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(title="✅ Utilisateur débanni", description=f"{user.mention} débanni", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du déban", ephemeral=True)

@admin_group.command(name="mute", description="Timeout un membre")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Aucune raison"):
    try:
        timeout_until = datetime.now() + timedelta(minutes=minutes)
        await member.timeout(timeout_until, reason=reason)
        embed = discord.Embed(title="🔇 Membre timeout", description=f"{member.mention} timeout {minutes}min", color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du timeout", ephemeral=True)

@admin_group.command(name="unmute", description="Retirer le timeout")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        embed = discord.Embed(title="🔊 Timeout retiré", description=f"{member.mention} peut parler", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur", ephemeral=True)

@admin_group.command(name="clear", description="Supprimer des messages")
async def clear(interaction: discord.Interaction, amount: int = 10):
    try:
        await interaction.response.defer()
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        await interaction.followup.send(f"🧹 {len(deleted)} messages supprimés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur", ephemeral=True)

# SYSTÈME D'AVERTISSEMENTS
@admin_group.command(name="warn", description="Avertir un membre")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    user_id = str(member.id)
    
    if user_id not in data["warns"]:
        data["warns"][user_id] = []

    warn_data = {
        "reason": reason,
        "moderator": interaction.user.name,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    data["warns"][user_id].append(warn_data)
    save_server_data(guild_id, data)

    embed = discord.Embed(title="⚠️ Avertissement", color=0xffff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Raison", value=reason)
    embed.add_field(name="Total warns", value=len(data["warns"][user_id]))

    await interaction.response.send_message(embed=embed)

    # Auto-sanction selon le nombre de warns
    warn_count = len(data["warns"][user_id])
    if warn_count >= 3:
        try:
            await member.ban(reason="3 avertissements atteints")
            await interaction.followup.send(f"🔨 {member.mention} banni automatiquement (3 warns)")
        except:
            pass

@admin_group.command(name="warns", description="Voir les avertissements d'un membre")
async def view_warns(interaction: discord.Interaction, member: discord.Member):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    user_id = str(member.id)
    warns = data["warns"].get(user_id, [])

    if not warns:
        return await interaction.response.send_message(f"{member.mention} n'a aucun avertissement", ephemeral=True)

    embed = discord.Embed(title=f"⚠️ Avertissements de {member.name}", color=0xffff00)
    for i, warn in enumerate(warns, 1):
        embed.add_field(
            name=f"Warn #{i}",
            value=f"**Raison:** {warn['reason']}\n**Modérateur:** {warn['moderator']}\n**Date:** {warn['date']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="unwarn", description="Retirer un avertissement")
async def unwarn(interaction: discord.Interaction, member: discord.Member, warn_number: int):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    user_id = str(member.id)
    warns = data["warns"].get(user_id, [])

    if not warns or warn_number < 1 or warn_number > len(warns):
        return await interaction.response.send_message("❌ Numéro d'avertissement invalide", ephemeral=True)

    removed_warn = warns.pop(warn_number - 1)
    save_server_data(guild_id, data)
    
    embed = discord.Embed(title="✅ Avertissement retiré", color=0x00ff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Warn retiré", value=removed_warn['reason'])

    await interaction.response.send_message(embed=embed)

# COMMANDES DE SÉCURITÉ AVANCÉES
@admin_group.command(name="lockdown", description="Verrouiller le serveur")
async def lockdown(interaction: discord.Interaction, reason: str = "Urgence sécuritaire"):
    await interaction.response.send_message("🔒 **INITIALISATION DU VERROUILLAGE...**", ephemeral=True)

    try:
        # Créer l'embed cinématique
        lockdown_embed = discord.Embed(
            title="🚨 ⚠️ **ALERTE SÉCURITÉ MAXIMALE** ⚠️ 🚨",
            description=f"```diff\n- SERVEUR EN VERROUILLAGE TOTAL\n- ACCÈS COMMUNICATION SUSPENDU\n- SEULS LES ADMINISTRATEURS AUTORISÉS\n```\n\n**📋 RAISON:** `{reason}`\n**🔐 STATUT:** `VERROUILLÉ`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}",
            color=0xff0000
        )
        lockdown_embed.set_image(url="https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif")
        lockdown_embed.set_thumbnail(url="https://media.giphy.com/media/xTiTnHXbRoaZ1B1Mo8/giphy.gif")
        lockdown_embed.add_field(
            name="🛡️ **PROTOCOLE DE SÉCURITÉ ACTIVÉ**",
            value="```yaml\n✅ Communications bloquées\n✅ Permissions révoquées\n✅ Surveillance active\n✅ Mode défensif engagé```",
            inline=False
        )
        lockdown_embed.set_footer(text="🔒 SYSTÈME DE SÉCURITÉ ASTRAL | VERROUILLAGE TOTAL ENGAGÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")

        # Verrouiller tous les canaux
        locked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                locked_channels += 1
            except:
                pass

        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚨" * 10)
                await channel.send(embed=lockdown_embed)
                await channel.send("🚨" * 10)
            except:
                pass

        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **VERROUILLAGE TERMINÉ** - {locked_channels} canaux sécurisés", ephemeral=True)

    except Exception as e:
        await interaction.followup.send("❌ Erreur lors du verrouillage", ephemeral=True)

@admin_group.command(name="unlock", description="Déverrouiller le serveur")
async def unlock(interaction: discord.Interaction):
    await interaction.response.send_message("🔓 **INITIALISATION DU DÉVERROUILLAGE...**", ephemeral=True)

    try:
        # Créer l'embed cinématique
        unlock_embed = discord.Embed(
            title="🎉 ✨ **LIBÉRATION TOTALE** ✨ 🎉",
            description=f"```diff\n+ SERVEUR DÉVERROUILLÉ AVEC SUCCÈS\n+ COMMUNICATIONS RÉTABLIES\n+ ACCÈS TOTAL RESTAURÉ\n```\n\n**🔓 STATUT:** `OPÉRATIONNEL`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}\n**💬 MESSAGE:** `Bienvenue de retour ! Le serveur est maintenant pleinement opérationnel.`",
            color=0x00ff66
        )
        unlock_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        unlock_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        unlock_embed.add_field(
            name="🎊 **SYSTÈME LIBÉRÉ**",
            value="```yaml\n✅ Communications rétablies\n✅ Permissions restaurées\n✅ Mode normal activé\n✅ Activité autorisée```",
            inline=False
        )
        unlock_embed.add_field(
            name="🌟 **STATUT DU SERVEUR**",
            value="```css\n[OPÉRATIONNEL] Toutes les fonctionnalités disponibles\n[SÉCURISÉ] Protection active maintenue\n[STABLE] Système en fonctionnement optimal```",
            inline=False
        )
        unlock_embed.set_footer(text="🔓 SYSTÈME DE SÉCURITÉ ASTRAL | ACCÈS TOTAL RESTAURÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")

        # Déverrouiller tous les canaux
        unlocked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=None)
                unlocked_channels += 1
            except:
                pass

        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10)
                await channel.send(embed=unlock_embed)
                await channel.send("🎊" * 10)
            except:
                pass

        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **DÉVERROUILLAGE TERMINÉ** - {unlocked_channels} canaux libérés", ephemeral=True)

    except Exception as e:
        await interaction.followup.send("❌ Erreur lors du déverrouillage", ephemeral=True)

@admin_group.command(name="nuke", description="Supprimer tous les messages du canal")
async def nuke(interaction: discord.Interaction):
    channel_name = interaction.channel.name
    channel_position = interaction.channel.position
    channel_category = interaction.channel.category

    # Message de préparation
    await interaction.response.send_message("💥 **PRÉPARATION DE LA DÉTONATION NUCLÉAIRE...**", ephemeral=True)

    # Countdown dramatique
    countdown_embed = discord.Embed(
        title="💣 ⚠️ **ALERTE DÉTONATION IMMINENTE** ⚠️ 💣",
        description="```diff\n- PRÉPARATION DE LA DESTRUCTION TOTALE\n- ÉVACUATION NUMÉRIQUE EN COURS\n- NETTOYAGE RADICAL IMMINENT\n```",
        color=0xff4500
    )
    countdown_embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
    countdown_embed.add_field(name="⚡ COMPTE À REBOURS", value="```css\n[3] INITIALISATION...\n[2] CHARGEMENT...\n[1] DÉTONATION...\n[0] BOOM! 💥```", inline=False)

    countdown_msg = await interaction.channel.send(embed=countdown_embed)

    # Attendre un peu pour l'effet dramatique
    await asyncio.sleep(3)

    try:
        await interaction.channel.delete()
        new_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            position=channel_position,
            category=channel_category
        )

        # Message post-nuke cinématique
        nuke_embed = discord.Embed(
            title="🌋 💥 **DÉTONATION RÉUSSIE** 💥 🌋",
            description=f"```diff\n+ CANAL COMPLÈTEMENT PURIFIÉ\n+ DESTRUCTION TOTALE ACCOMPLIE\n+ RENAISSANCE NUMÉRIQUE INITIÉE\n```\n\n**💣 OPÉRATION:** `NUKE COMPLÈTE`\n**🔥 CANAL:** `#{channel_name}`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 OPÉRATEUR:** {interaction.user.mention}",
            color=0xff0000
        )
        nuke_embed.set_image(url="https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif")
        nuke_embed.set_thumbnail(url="https://media.giphy.com/media/l46CyJmS9KUbokzsI/giphy.gif")
        nuke_embed.add_field(
            name="☢️ **RAPPORT DE DÉTONATION**",
            value="```yaml\n✅ Messages éliminés: TOUS\n✅ Historique effacé: COMPLET\n✅ Canal purifié: 100%\n✅ Reconstruction: TERMINÉE```",
            inline=False
        )
        nuke_embed.add_field(
            name="🔄 **STATUT POST-APOCALYPSE**",
            value="```css\n[NOUVEAU] Canal fraîchement recréé\n[PROPRE] Aucun message résiduel\n[PRÊT] Disponible pour utilisation```",
            inline=False
        )
        nuke_embed.set_footer(text="💥 SYSTÈME DE PURIFICATION ASTRAL | NUKE RÉUSSI", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")

        await new_channel.send("💥" * 15)
        await new_channel.send(embed=nuke_embed)
        await new_channel.send("☢️" * 15)
        await new_channel.send("**🎉 BIENVENUE DANS LE NOUVEAU CANAL PURIFIÉ ! 🎉**")

    except Exception as e:
        pass

@admin_group.command(name="massban", description="Bannir plusieurs utilisateurs")
async def massban(interaction: discord.Interaction, user_ids: str, reason: str = "Ban de masse"):
    await interaction.response.defer()

    ids = user_ids.split()
    banned_count = 0

    for user_id in ids:
        try:
            user = await bot.fetch_user(int(user_id))
            await interaction.guild.ban(user, reason=reason)
            banned_count += 1
        except:
            continue

    embed = discord.Embed(title="🔨 Ban de masse", description=f"{banned_count} utilisateurs bannis", color=0xff0000)
    await interaction.followup.send(embed=embed)

@admin_group.command(name="antiraid", description="Activer/désactiver la protection anti-raid")
async def antiraid(interaction: discord.Interaction, enabled: bool = True):
    guild_id = interaction.guild.id
    update_server_data(guild_id, "raid_protection", enabled)

    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🛡️ Protection Anti-Raid", description=f"Protection {status}", color=color)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="automod", description="Activer/désactiver l'automodération")
async def automod(interaction: discord.Interaction, enabled: bool = True):
    guild_id = interaction.guild.id
    update_server_data(guild_id, "automod_enabled", enabled)

    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🤖 Automodération", description=f"Automod {status}", color=color)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="addword", description="Ajouter un mot banni")
async def addword(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    
    if word.lower() not in data["banned_words"]:
        data["banned_words"].append(word.lower())
        save_server_data(guild_id, data)
        embed = discord.Embed(title="🚫 Mot ajouté", description=f"'{word}' ajouté aux mots bannis", color=0xff6b6b)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot est déjà banni", color=0xff0000)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="removeword", description="Retirer un mot banni")
async def removeword(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    
    if word.lower() in data["banned_words"]:
        data["banned_words"].remove(word.lower())
        save_server_data(guild_id, data)
        embed = discord.Embed(title="✅ Mot retiré", description=f"'{word}' retiré des mots bannis", color=0x00ff00)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot n'est pas dans la liste", color=0xff0000)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="bannedwords", description="Voir la liste des mots bannis")
async def bannedwords(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    
    if not data["banned_words"]:
        return await interaction.response.send_message("Aucun mot banni", ephemeral=True)

    embed = discord.Embed(title="🚫 Mots bannis", description="\n".join(data["banned_words"]), color=0xff6b6b)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="securityscan", description="Scanner les membres suspects")
async def security_scan(interaction: discord.Interaction):
    await interaction.response.defer()
    
    suspects = []
    recent_joins = []
    
    for member in interaction.guild.members:
        if member.bot:
            continue
            
        # Compte récent (moins de 7 jours)
        account_age = datetime.now() - member.created_at.replace(tzinfo=None)
        if account_age.days < 7:
            recent_joins.append(member)
        
        # Profil suspect (pas d'avatar, nom bizarre)
        if not member.avatar or len([c for c in member.name if not c.isascii()]) > 5:
            suspects.append(member)
    
    embed = discord.Embed(title="🔍 SCAN DE SÉCURITÉ", color=0xff0000)
    embed.add_field(name="👤 Comptes récents (<7j)", value=len(recent_joins), inline=True)
    embed.add_field(name="⚠️ Profils suspects", value=len(suspects), inline=True)
    embed.add_field(name="📊 Total membres", value=interaction.guild.member_count, inline=True)
    
    if recent_joins[:10]:  # Max 10
        recent_list = "\n".join([f"{m.mention} ({(datetime.now() - m.created_at.replace(tzinfo=None)).days}j)" for m in recent_joins[:10]])
        embed.add_field(name="🕐 Comptes récents", value=recent_list, inline=False)
    
    if suspects[:10]:  # Max 10
        suspect_list = "\n".join([f"{m.mention} - {m.name}" for m in suspects[:10]])
        embed.add_field(name="🚨 Profils suspects", value=suspect_list, inline=False)
    
    await interaction.followup.send(embed=embed)
    await log_action(interaction.guild, "security", interaction.user, details="Scan de sécurité effectué")

@admin_group.command(name="quarantine", description="Isoler un membre suspect")
async def quarantine(interaction: discord.Interaction, member: discord.Member, reason: str = "Comportement suspect"):
    try:
        # Retirer tous les rôles sauf @everyone
        roles_removed = []
        for role in member.roles[1:]:  # Skip @everyone
            if role < interaction.guild.me.top_role:
                await member.remove_roles(role)
                roles_removed.append(role.name)
        
        # Timeout 24h
        await member.timeout(datetime.now() + timedelta(hours=24), reason=f"Quarantaine: {reason}")
        
        embed = discord.Embed(title="🚨 QUARANTAINE", color=0xff4500)
        embed.add_field(name="Membre", value=member.mention, inline=True)
        embed.add_field(name="Raison", value=reason, inline=True)
        embed.add_field(name="Durée", value="24 heures", inline=True)
        embed.add_field(name="Rôles retirés", value=", ".join(roles_removed) if roles_removed else "Aucun", inline=False)
        
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "security", interaction.user, member, reason, f"Quarantaine - Rôles retirés: {', '.join(roles_removed)}")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur quarantaine: {str(e)}", ephemeral=True)

@admin_group.command(name="logs", description="Voir les derniers logs de sécurité")
async def view_logs(interaction: discord.Interaction, limit: int = 10):
    guild_id = interaction.guild.id
    data = get_server_data(guild_id)
    log_channel_id = data.get("log_channel_id")
    
    if not log_channel_id:
        return await interaction.response.send_message("❌ Aucun canal de logs configuré", ephemeral=True)
    
    log_channel = bot.get_channel(log_channel_id)
    if not log_channel:
        return await interaction.response.send_message("❌ Canal de logs introuvable", ephemeral=True)
    
    try:
        messages = []
        async for message in log_channel.history(limit=min(limit, 50)):
            if message.embeds and message.author == bot.user:
                embed = message.embeds[0]
                if "LOG DE SÉCURITÉ" in embed.title:
                    messages.append(message)
        
        if not messages:
            return await interaction.response.send_message("Aucun log récent trouvé", ephemeral=True)
        
        embed = discord.Embed(title="📋 DERNIERS LOGS", color=0x0099ff)
        
        for i, msg in enumerate(messages[:limit], 1):
            log_embed = msg.embeds[0]
            action = next((field.value for field in log_embed.fields if field.name == "Action"), "Inconnue")
            moderator = next((field.value for field in log_embed.fields if field.name == "Modérateur"), "Inconnu")
            
            embed.add_field(
                name=f"#{i} - {action}",
                value=f"Par: {moderator}\n<t:{int(msg.created_at.timestamp())}:R>",
                inline=True
            )
        
        embed.set_footer(text=f"Affichage des {len(messages)} derniers logs")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lecture logs: {str(e)}", ephemeral=True)

@admin_group.command(name="backup", description="Sauvegarder la configuration du serveur")
async def backup_config(interaction: discord.Interaction):
    try:
        guild_id = interaction.guild.id
        data = get_server_data(guild_id)
        
        # Créer un backup avec timestamp
        backup_data = {
            "server_name": interaction.guild.name,
            "server_id": guild_id,
            "backup_date": datetime.now().isoformat(),
            "config": data,
            "channels": [{"name": c.name, "id": c.id, "type": str(c.type)} for c in interaction.guild.channels],
            "roles": [{"name": r.name, "id": r.id, "permissions": r.permissions.value} for r in interaction.guild.roles]
        }
        
        # Sauvegarder
        backup_file = f"configs/backup_{guild_id}_{int(datetime.now().timestamp())}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)
        
        embed = discord.Embed(title="💾 SAUVEGARDE", color=0x00ff00)
        embed.add_field(name="Statut", value="✅ Sauvegarde créée", inline=True)
        embed.add_field(name="Fichier", value=backup_file, inline=True)
        embed.add_field(name="Taille", value=f"{len(json.dumps(backup_data))} caractères", inline=True)
        
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, "security", interaction.user, details="Sauvegarde de configuration créée")
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur sauvegarde: {str(e)}", ephemeral=True)

# COMMANDES SYSTÈME
@admin_group.command(name="maintenance", description="Mode maintenance ON")
async def maintenance_on(interaction: discord.Interaction, reason: str = "Maintenance"):
    guild_id = interaction.guild.id
    update_server_data(guild_id, "maintenance_mode", True)
    update_server_data(guild_id, "maintenance_reason", reason)

    await interaction.response.send_message("🔧 **INITIALISATION DU MODE MAINTENANCE...**", ephemeral=True)

    try:
        # Créer l'embed cinématique de maintenance
        maintenance_embed = discord.Embed(
            title="🚧 ⚠️ **MAINTENANCE EN COURS** ⚠️ 🚧",
            description=f"```diff\n- SERVEUR EN MAINTENANCE TECHNIQUE\n- ACCÈS UTILISATEUR SUSPENDU\n- INTERVENTIONS ADMINISTRATIVES EN COURS\n```\n\n**🔧 RAISON:** `{reason}`\n**⚙️ STATUT:** `MAINTENANCE ACTIVE`\n**⏰ DÉBUT:** <t:{int(datetime.now().timestamp())}:F>\n**👨‍💻 TECHNICIEN:** {interaction.user.mention}",
            color=0xffa500
        )
        maintenance_embed.set_image(url="https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif")
        maintenance_embed.set_thumbnail(url="https://media.giphy.com/media/xTiTnHXbRoaZ1B1Mo8/giphy.gif")
        maintenance_embed.add_field(
            name="⚙️ **OPÉRATIONS EN COURS**",
            value="```yaml\n🔧 Maintenance système active\n🛠️ Interventions techniques\n🔄 Optimisations serveur\n⏸️ Communications suspendues```",
            inline=False
        )
        maintenance_embed.add_field(
            name="🚫 **RESTRICTIONS ACTIVES**",
            value="```css\n[BLOQUÉ] Messages utilisateurs\n[AUTORISÉ] Communications admin\n[ACTIF] Surveillance système\n[STANDBY] Fonctions normales```",
            inline=False
        )
        maintenance_embed.add_field(
            name="📋 **INFORMATIONS**",
            value=f"```fix\nDurée estimée: En cours d'évaluation\nImpact: Communications temporairement suspendues\nContact: Équipe administrative disponible```",
            inline=False
        )
        maintenance_embed.set_footer(text="🔧 SYSTÈME DE MAINTENANCE ASTRAL | MODE TECHNIQUE ACTIVÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")

        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚧" * 10)
                await channel.send(embed=maintenance_embed)
                await channel.send("⚙️" * 10)
            except:
                pass

        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **MODE MAINTENANCE ACTIVÉ** - Serveur en maintenance technique", ephemeral=True)

    except Exception as e:
        await interaction.followup.send("❌ Erreur lors de l'activation maintenance", ephemeral=True)

@admin_group.command(name="maintenance_off", description="Mode maintenance OFF")
async def maintenance_off(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    update_server_data(guild_id, "maintenance_mode", False)

    await interaction.response.send_message("✅ **FINALISATION DE LA MAINTENANCE...**", ephemeral=True)

    try:
        # Créer l'embed cinématique de fin de maintenance
        end_maintenance_embed = discord.Embed(
            title="🎉 ✨ **MAINTENANCE TERMINÉE** ✨ 🎉",
            description=f"```diff\n+ MAINTENANCE TECHNIQUE COMPLÉTÉE\n+ SERVEUR PLEINEMENT OPÉRATIONNEL\n+ COMMUNICATIONS RÉTABLIES\n```\n\n**✅ STATUT:** `OPÉRATIONNEL`\n**⏰ FIN:** <t:{int(datetime.now().timestamp())}:F>\n**👨‍💻 TECHNICIEN:** {interaction.user.mention}\n**🔄 RÉSULTAT:** `Maintenance réussie - Système optimisé`",
            color=0x00ff66
        )
        end_maintenance_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        end_maintenance_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        end_maintenance_embed.add_field(
            name="🎊 **MAINTENANCE RÉUSSIE**",
            value="```yaml\n✅ Système entièrement opérationnel\n✅ Communications restaurées\n✅ Optimisations appliquées\n✅ Serveur stabilisé```",
            inline=False
        )
        end_maintenance_embed.add_field(
            name="🌟 **AMÉLIORATIONS APPORTÉES**",
            value="```css\n[OPTIMISÉ] Performances système\n[SÉCURISÉ] Protocoles de sécurité\n[STABLE] Fonctionnement optimal\n[DISPONIBLE] Toutes fonctionnalités```",
            inline=False
        )
        end_maintenance_embed.add_field(
            name="📢 **ANNONCE**",
            value="```fix\nLe serveur est maintenant pleinement fonctionnel !\nMerci de votre patience pendant la maintenance.\nToutes les fonctionnalités sont disponibles.```",
            inline=False
        )
        end_maintenance_embed.set_footer(text="✅ SYSTÈME DE MAINTENANCE ASTRAL | SERVEUR OPÉRATIONNEL", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")

        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10)
                await channel.send(embed=end_maintenance_embed)
                await channel.send("🎊" * 10)
                await channel.send("**🚀 LE SERVEUR EST DE RETOUR ! BIENVENUE ! 🚀**")
            except:
                pass

        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **MAINTENANCE TERMINÉE** - Serveur pleinement opérationnel", ephemeral=True)

    except Exception as e:
        await interaction.followup.send("❌ Erreur lors de la fin de maintenance", ephemeral=True)

@admin_group.command(name="setlogchannel", description="Définir le canal de logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    update_server_data(guild_id, "log_channel_id", channel.id)

    embed = discord.Embed(title="📝 Canal de logs défini", description=f"Logs dans {channel.mention}", color=0x0099ff)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Informations du serveur")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=0x0099ff)
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Canaux", value=len(guild.channels))
    embed.add_field(name="Rôles", value=len(guild.roles))
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Propriétaire", value=guild.owner.mention if guild.owner else "Inconnu")
    embed.add_field(name="Niveau de vérification", value=str(guild.verification_level).title())

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Informations d'un utilisateur")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user

    embed = discord.Embed(title=f"👤 {member.name}", color=member.color)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Surnom", value=member.nick or "Aucun")
    embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Compte créé", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Rôles", value=len(member.roles) - 1)
    embed.add_field(name="Status", value=str(member.status).title())

    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    await interaction.response.send_message(embed=embed)

@admin_group.command(name="say", description="Faire parler le bot")
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel

    try:
        await target_channel.send(message)
        embed = discord.Embed(
            title="✅ Message envoyé",
            description=f"Message envoyé dans {target_channel.mention}",
            color=0x00ff00
        )
        embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
        embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Canal", value=target_channel.mention, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log dans le canal de logs si configuré
        guild_id = interaction.guild.id
        data = get_server_data(guild_id)
        log_channel_id = data["log_channel_id"]
        
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(
                    title="📤 Message bot envoyé",
                    description=f"Message envoyé via le bot dans {target_channel.mention}",
                    color=0x0099ff
                )
                log_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Heure", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
                await log_channel.send(embed=log_embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="embed", description="Envoyer un message embed via le bot")
async def send_embed(interaction: discord.Interaction, title: str, description: str, channel: discord.TextChannel = None, color: str = "0x0099ff"):
    target_channel = channel or interaction.channel

    try:
        # Convertir la couleur
        try:
            embed_color = int(color, 16) if color.startswith("0x") else int(color, 16)
        except:
            embed_color = 0x0099ff

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Message officiel • {interaction.guild.name}")

        await target_channel.send(embed=embed)

        # Confirmation
        confirm_embed = discord.Embed(
            title="✅ Embed envoyé",
            description=f"Embed envoyé dans {target_channel.mention}",
            color=0x00ff00
        )
        confirm_embed.add_field(name="Titre", value=title, inline=False)
        confirm_embed.add_field(name="Description", value=description[:1000], inline=False)
        confirm_embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        # Log
        guild_id = interaction.guild.id
        data = get_server_data(guild_id)
        log_channel_id = data["log_channel_id"]
        
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(
                    title="📤 Embed bot envoyé",
                    description=f"Embed envoyé via le bot dans {target_channel.mention}",
                    color=0x0099ff
                )
                log_embed.add_field(name="Titre", value=title, inline=False)
                log_embed.add_field(name="Description", value=description[:1000], inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                await log_channel.send(embed=log_embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="announce", description="Envoyer une annonce officielle")
async def announce(interaction: discord.Interaction, title: str, message: str, channel: discord.TextChannel = None, ping_everyone: bool = False):
    target_channel = channel or interaction.channel

    try:
        # Créer l'embed d'annonce
        announce_embed = discord.Embed(
            title=f"📢 {title}",
            description=message,
            color=0xffd700,
            timestamp=datetime.now()
        )
        announce_embed.set_footer(text=f"Annonce officielle • {interaction.guild.name}")
        announce_embed.set_author(name="ANNONCE OFFICIELLE", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        # Ajouter une image d'annonce
        announce_embed.set_thumbnail(url="https://media.giphy.com/media/l0HlQoLBxzlnKRT8s/giphy.gif")

        # Envoyer avec ou sans ping
        content = "@everyone" if ping_everyone else ""

        await target_channel.send("🔔" * 10)
        await target_channel.send(content=content, embed=announce_embed)
        await target_channel.send("🔔" * 10)

        # Confirmation
        confirm_embed = discord.Embed(
            title="✅ Annonce publiée",
            description=f"Annonce envoyée dans {target_channel.mention}",
            color=0x00ff00
        )
        confirm_embed.add_field(name="Titre", value=title, inline=False)
        confirm_embed.add_field(name="Message", value=message[:1000], inline=False)
        confirm_embed.add_field(name="Ping everyone", value="Oui" if ping_everyone else "Non", inline=True)

        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        # Log
        guild_id = interaction.guild.id
        data = get_server_data(guild_id)
        log_channel_id = data["log_channel_id"]
        
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(
                    title="📢 Annonce officielle publiée",
                    description=f"Annonce publiée dans {target_channel.mention}",
                    color=0xffd700
                )
                log_embed.add_field(name="Titre", value=title, inline=False)
                log_embed.add_field(name="Message", value=message[:1000], inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Ping everyone", value="Oui" if ping_everyone else "Non", inline=True)
                await log_channel.send(embed=log_embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="dm", description="Envoyer un MP à un utilisateur via le bot")
async def send_dm(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        # Créer l'embed pour le MP
        dm_embed = discord.Embed(
            title="📨 Message du serveur",
            description=message,
            color=0x0099ff,
            timestamp=datetime.now()
        )
        dm_embed.set_footer(text=f"Message officiel de {interaction.guild.name}")
        dm_embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        await member.send(embed=dm_embed)

        # Confirmation
        confirm_embed = discord.Embed(
            title="✅ MP envoyé",
            description=f"Message privé envoyé à {member.mention}",
            color=0x00ff00
        )
        confirm_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
        confirm_embed.add_field(name="Destinataire", value=member.mention, inline=True)
        confirm_embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

        # Log
        guild_id = interaction.guild.id
        data = get_server_data(guild_id)
        log_channel_id = data["log_channel_id"]
        
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="📨 MP bot envoyé",
                    description=f"Message privé envoyé via le bot à {member.mention}",
                    color=0x0099ff
                )
                log_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
                log_embed.add_field(name="Destinataire", value=member.mention, inline=True)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                await log_channel.send(embed=log_embed)

    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Impossible d'envoyer un MP à {member.mention} (MP fermés)", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@bot.tree.command(name="commands", description="Liste détaillée des commandes")
async def commands_list(interaction: discord.Interaction):
    embeds = []

    if interaction.user.guild_permissions.administrator:
        # Embed 1: Modération de base
        embed1 = discord.Embed(title="🔨 MODÉRATION DE BASE", color=0xff6b6b)
        embed1.add_field(
            name="/kick [membre] [raison]",
            value="Exclure un membre du serveur (il peut revenir avec une invitation)",
            inline=False
        )
        embed1.add_field(
            name="/ban [membre] [raison]",
            value="Bannir définitivement un membre (ne peut plus rejoindre)",
            inline=False
        )
        embed1.add_field(
            name="/unban [ID_utilisateur] [raison]",
            value="Débannir un utilisateur avec son ID Discord",
            inline=False
        )
        embed1.add_field(
            name="/mute [membre] [minutes] [raison]",
            value="Timeout un membre (ne peut plus parler pendant X minutes)",
            inline=False
        )
        embed1.add_field(
            name="/unmute [membre]",
            value="Retirer le timeout d'un membre",
            inline=False
        )
        embed1.add_field(
            name="/clear [nombre]",
            value="Supprimer X messages du canal (max 100)",
            inline=False
        )
        embeds.append(embed1)

        # Embed 2: Système d'avertissements
        embed2 = discord.Embed(title="⚠️ SYSTÈME D'AVERTISSEMENTS", color=0xffff00)
        embed2.add_field(
            name="/warn [membre] [raison]",
            value="Donner un avertissement à un membre (ban auto à 3 warns)",
            inline=False
        )
        embed2.add_field(
            name="/warns [membre]",
            value="Voir tous les avertissements d'un membre",
            inline=False
        )
        embed2.add_field(
            name="/unwarn [membre] [numéro]",
            value="Retirer un avertissement spécifique d'un membre",
            inline=False
        )
        embeds.append(embed2)

        # Embed 3: Sécurité avancée
        embed3 = discord.Embed(title="🛡️ SÉCURITÉ AVANCÉE", color=0xff0000)
        embed3.add_field(
            name="/lockdown [raison]",
            value="🚨 Verrouiller TOUT le serveur avec alerte ROUGE dans tous les canaux",
            inline=False
        )
        embed3.add_field(
            name="/unlock",
            value="🎉 Déverrouiller le serveur avec célébration dans tous les canaux",
            inline=False
        )
        embed3.add_field(
            name="/nuke",
            value="💥 SUPPRIMER TOUS les messages + compte à rebours dramatique",
            inline=False
        )
        embed3.add_field(
            name="/massban [IDs séparés par espaces] [raison]",
            value="🔨 Bannir plusieurs utilisateurs en une fois avec leurs IDs",
            inline=False
        )
        embed3.add_field(
            name="/antiraid [true/false]",
            value="🛡️ Protection auto (ban comptes récents <7j)",
            inline=False
        )
        embed3.add_field(
            name="🎭 Effets cinématiques :",
            value="• Lockdown: Embeds rouges + GIFs d'alerte\n• Unlock: Embeds verts + GIFs de célébration\n• Nuke: Countdown + explosion visuelle\n• Annonces dans TOUS les canaux texte",
            inline=False
        )
        embeds.append(embed3)

        # Embed 4: Automodération
        embed4 = discord.Embed(title="🤖 AUTOMODÉRATION", color=0x9932cc)
        embed4.add_field(
            name="/automod [true/false]",
            value="Activer/désactiver la modération automatique",
            inline=False
        )
        embed4.add_field(
            name="/addword [mot]",
            value="Ajouter un mot à la liste des mots interdits",
            inline=False
        )
        embed4.add_field(
            name="/removeword [mot]",
            value="Retirer un mot de la liste des mots interdits",
            inline=False
        )
        embed4.add_field(
            name="/bannedwords",
            value="Voir la liste complète des mots interdits",
            inline=False
        )
        embed4.add_field(
            name="🔧 Protections automatiques :",
            value="• Anti-spam (timeout 5min si >10 msg/min)\n• Anti-mentions (max 5 mentions/msg)\n• Filtrage mots interdits\n• Blocage pendant maintenance",
            inline=False
        )
        embeds.append(embed4)

        # Embed 5: Messages via bot
        embed5 = discord.Embed(title="📤 MESSAGES VIA BOT", color=0x00aaff)
        embed5.add_field(
            name="/say [message] [canal]",
            value="Faire dire un message au bot dans un canal spécifique",
            inline=False
        )
        embed5.add_field(
            name="/embed [titre] [description] [canal] [couleur]",
            value="Envoyer un message embed stylisé via le bot",
            inline=False
        )
        embed5.add_field(
            name="/announce [titre] [message] [canal] [ping_everyone]",
            value="Publier une annonce officielle avec style et émojis",
            inline=False
        )
        embed5.add_field(
            name="/dm [membre] [message]",
            value="Envoyer un message privé officiel à un membre",
            inline=False
        )
        embed5.add_field(
            name="📋 Fonctionnalités avancées :",
            value="• Tous les messages sont loggés automatiquement\n• Confirmations privées pour l'admin\n• Embeds avec timestamp et footer officiel\n• Support couleurs personnalisées (format hex)",
            inline=False
        )
        embeds.append(embed5)

        # Embed 6: Système
        embed6 = discord.Embed(title="⚙️ SYSTÈME & CONFIGURATION", color=0xffa500)
        embed6.add_field(
            name="/maintenance [raison]",
            value="🚧 Activer mode maintenance avec annonce CINÉMATIQUE dans tous les canaux",
            inline=False
        )
        embed6.add_field(
            name="/maintenance_off",
            value="✅ Désactiver mode maintenance avec célébration dans tous les canaux",
            inline=False
        )
        embed6.add_field(
            name="/setlogchannel [canal]",
            value="Définir le canal où les logs automatiques seront envoyés",
            inline=False
        )
        embed6.add_field(
            name="/serverinfo",
            value="Afficher les informations détaillées du serveur",
            inline=False
        )
        embed6.add_field(
            name="🎬 Effets visuels :",
            value="• Maintenance: Embeds orange avec GIFs techniques\n• Fin maintenance: Embeds verts avec GIFs festifs\n• Messages dans TOUS les canaux comme lockdown\n• Timestamps Discord en temps réel",
            inline=False
        )
        embeds.append(embed6)

    # Embed pour tous les utilisateurs
    embed_general = discord.Embed(title="📋 COMMANDES GÉNÉRALES", color=0x0099ff)
    embed_general.add_field(
        name="/commands",
        value="Afficher cette liste détaillée de toutes les commandes",
        inline=False
    )
    embed_general.add_field(
        name="/userinfo [membre]",
        value="Voir les informations d'un utilisateur (ou vous-même si aucun membre spécifié)",
        inline=False
    )

    if interaction.user.guild_permissions.administrator:
        embed_general.add_field(
            name="🔑 ACCÈS ADMIN",
            value="Vous avez accès à toutes les commandes de modération !",
            inline=False
        )
    else:
        embed_general.add_field(
            name="🚫 ACCÈS LIMITÉ",
            value="Vous n'avez accès qu'aux commandes générales",
            inline=False
        )

    embeds.append(embed_general)

    # Envoyer le premier embed
    await interaction.response.send_message(embed=embeds[0], ephemeral=True)

    # Envoyer les autres embeds
    for embed in embeds[1:]:
        await interaction.followup.send(embed=embed, ephemeral=True)

# ÉVÉNEMENTS DE SÉCURITÉ
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    guild_id = message.guild.id
    data = get_server_data(guild_id)

    # Bloquer messages en maintenance (sauf admins)
    if data["maintenance_mode"] and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
            await message.author.send(f"🔧 Serveur en maintenance: {data['maintenance_reason']}")
        except:
            pass
        return

    # Automodération
    if data["automod_enabled"] and not message.author.guild_permissions.administrator:
        # Vérifier mots bannis
        content_lower = message.content.lower()
        for word in data["banned_words"]:
            if word in content_lower:
                await message.delete()
                try:
                    await message.author.send(f"⚠️ Message supprimé: mot interdit détecté")
                except:
                    pass
                return

        # Anti-spam
        user_id = str(message.author.id)
        now = datetime.now()

        if user_id not in data["anti_spam"]:
            data["anti_spam"][user_id] = []

        # Nettoyer les anciens messages (plus d'1 minute) - convertir en timestamps
        current_messages = []
        for msg_time_str in data["anti_spam"][user_id]:
            try:
                msg_time = datetime.fromisoformat(msg_time_str)
                if (now - msg_time).seconds < 60:
                    current_messages.append(msg_time_str)
            except:
                continue
        
        data["anti_spam"][user_id] = current_messages

        # Ajouter ce message
        data["anti_spam"][user_id].append(now.isoformat())
        
        # Sauvegarder les données mises à jour
        save_server_data(guild_id, data)

        # Vérifier spam
        if len(data["anti_spam"][user_id]) > data["max_messages_per_minute"]:
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=5), reason="Spam détecté")
                await message.channel.send(f"🔇 {message.author.mention} timeout pour spam (5min)")
                await log_action(message.guild, "spam_detected", bot.user, message.author, "Spam détecté", f"{len(data['anti_spam'][user_id])} messages en 1 minute")
            except:
                pass

        # Vérifier mentions excessives
        if len(message.mentions) > data["max_mentions"]:
            await message.delete()
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=2), reason="Mentions excessives")
            except:
                pass

    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    data = get_server_data(guild_id)
    
    if data["raid_protection"]:
        # Vérifier compte récent (moins de 7 jours)
        account_age = datetime.now() - member.created_at.replace(tzinfo=None)
        if account_age.days < 7:
            try:
                await member.ban(reason="Protection anti-raid: compte trop récent")
                log_channel_id = data["log_channel_id"]
                if log_channel_id:
                    channel = bot.get_channel(log_channel_id)
                    if channel:
                        embed = discord.Embed(title="🛡️ Anti-raid", description=f"{member.mention} banni (compte récent)", color=0xff0000)
                        await channel.send(embed=embed)
            except:
                pass

@bot.event
async def on_member_remove(member):
    guild_id = member.guild.id
    data = get_server_data(guild_id)
    log_channel_id = data["log_channel_id"]
    
    if log_channel_id:
        channel = bot.get_channel(log_channel_id)
        if channel:
            embed = discord.Embed(title="👋 Membre parti", description=f"{member.name} a quitté", color=0xffa500)
            await channel.send(embed=embed)

# DÉMARRAGE
if __name__ == "__main__":
    # Initialisation du système de logs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Chargement des variables d'environnement
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        logging.critical("❌ Token manquant! Définissez la variable DISCORD_BOT_TOKEN dans .env")
        exit(1)

    # Configuration des dossiers
    os.makedirs('configs', exist_ok=True)

    # Gestion des erreurs spécifiques
    try:
        logging.info("🚀 Démarrage du bot...")
        bot.run(token)
    except discord.errors.LoginFailure:
        logging.critical("🔑 Token invalide! Vérifiez votre token Discord")
        exit(1)
    except KeyboardInterrupt:
        logging.info("🛑 Arrêt manuel du bot")
        exit(0)
    except Exception as e:
        logging.error(f"💥 Erreur inattendue: {str(e)}")
        exit(1)

    except Exception as e:
        logging.error(f"💥 Erreur inattendue: {str(e)}")
        exit(1)
