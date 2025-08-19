import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio
import logging

# Configuration du logging pour Debian
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Chargement des configurations
def load_config(guild_id):
    try:
        with open(f'configs/{guild_id}.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuration par défaut
        default_config = {
            "LOG_CHANNEL_ID": None,
            "MAINTENANCE_MODE": False,
            "MAINTENANCE_REASON": "",
            "ANTI_SPAM": {},
            "WARNS": {},
            "AUTOMOD_ENABLED": True,
            "RAID_PROTECTION": True,
            "BANNED_WORDS": ["spam", "hack", "scam"],
            "MAX_MENTIONS": 5,
            "MAX_MESSAGES_PER_MINUTE": 10
        }
        save_config(guild_id, default_config)
        return default_config

def save_config(guild_id, config):
    os.makedirs('configs', exist_ok=True)
    with open(f'configs/{guild_id}.json', 'w') as f:
        json.dump(config, f, indent=4)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} est connecté!')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')

# Fonction helper pour les commandes
def get_guild_config(guild_id):
    return load_config(guild_id)

def update_guild_config(guild_id, key, value):
    config = load_config(guild_id)
    config[key] = value
    save_config(guild_id, config)

# COMMANDES MODIFIÉES POUR UTILISER LA CONFIG PAR SERVEUR
@bot.tree.command(name="addword", description="Ajouter un mot banni")
async def addword(interaction: discord.Interaction, word: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    config = get_guild_config(interaction.guild.id)
    banned_words = config["BANNED_WORDS"]
    
    if word.lower() not in banned_words:
        banned_words.append(word.lower())
        update_guild_config(interaction.guild.id, "BANNED_WORDS", banned_words)
        embed = discord.Embed(title="🚫 Mot ajouté", description=f"'{word}' ajouté aux mots bannis", color=0xff6b6b)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot est déjà banni", color=0xff0000)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="removeword", description="Retirer un mot banni")
async def removeword(interaction: discord.Interaction, word: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    config = get_guild_config(interaction.guild.id)
    banned_words = config["BANNED_WORDS"]
    
    if word.lower() in banned_words:
        banned_words.remove(word.lower())
        update_guild_config(interaction.guild.id, "BANNED_WORDS", banned_words)
        embed = discord.Embed(title="✅ Mot retiré", description=f"'{word}' retiré des mots bannis", color=0x00ff00)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot n'est pas dans la liste", color=0xff0000)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="bannedwords", description="Voir la liste des mots bannis")
async def bannedwords(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    config = get_guild_config(interaction.guild.id)
    banned_words = config["BANNED_WORDS"]
    
    if not banned_words:
        return await interaction.response.send_message("Aucun mot banni", ephemeral=True)
    
    embed = discord.Embed(title="🚫 Mots bannis", description="\n".join(banned_words), color=0xff6b6b)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="automod", description="Activer/désactiver l'automodération")
async def automod(interaction: discord.Interaction, enabled: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    update_guild_config(interaction.guild.id, "AUTOMOD_ENABLED", enabled)
    
    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🤖 Automodération", description=f"Automod {status}", color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="antiraid", description="Activer/désactiver la protection anti-raid")
async def antiraid(interaction: discord.Interaction, enabled: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    update_guild_config(interaction.guild.id, "RAID_PROTECTION", enabled)
    
    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🛡️ Protection Anti-Raid", description=f"Protection {status}", color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setlogchannel", description="Définir le canal de logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    update_guild_config(interaction.guild.id, "LOG_CHANNEL_ID", channel.id)
    
    embed = discord.Embed(title="📝 Canal de logs défini", description=f"Logs dans {channel.mention}", color=0x0099ff)
    await interaction.response.send_message(embed=embed)

# ÉVÉNEMENTS MODIFIÉS POUR UTILISER LA CONFIG PAR SERVEUR
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    config = get_guild_config(message.guild.id)
    
    # Bloquer messages en maintenance (sauf admins)
    if config["MAINTENANCE_MODE"] and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
            await message.author.send(f"🔧 Serveur en maintenance: {config['MAINTENANCE_REASON']}")
        except:
            pass
        return
    
    # Automodération
    if config["AUTOMOD_ENABLED"] and not message.author.guild_permissions.administrator:
        # Vérifier mots bannis
        content_lower = message.content.lower()
        for word in config["BANNED_WORDS"]:
            if word in content_lower:
                await message.delete()
                try:
                    await message.author.send(f"⚠️ Message supprimé: mot interdit détecté")
                except:
                    pass
                return
        
        # Anti-spam
        user_id = message.author.id
        now = datetime.now()
        anti_spam = config["ANTI_SPAM"]
        
        if user_id not in anti_spam:
            anti_spam[user_id] = []
        
        # Nettoyer les anciens messages (plus d'1 minute)
        anti_spam[user_id] = [msg_time for msg_time in anti_spam[user_id] 
                             if (now - datetime.fromisoformat(msg_time)).seconds < 60]
        
        # Ajouter ce message (sérialisé en string)
        anti_spam[user_id].append(now.isoformat())
        update_guild_config(message.guild.id, "ANTI_SPAM", anti_spam)
        
        # Vérifier spam
        if len(anti_spam[user_id]) > config["MAX_MESSAGES_PER_MINUTE"]:
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=5), reason="Spam détecté")
                await message.channel.send(f"🔇 {message.author.mention} timeout pour spam (5min)")
            except:
                pass
        
        # Vérifier mentions excessives
        if len(message.mentions) > config["MAX_MENTIONS"]:
            await message.delete()
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=2), reason="Mentions excessives")
            except:
                pass
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    config = get_guild_config(member.guild.id)
    
    if config["RAID_PROTECTION"]:
        # Vérifier compte récent (moins de 7 jours)
        account_age = datetime.now() - member.created_at.replace(tzinfo=None)
        if account_age.days < 7:
            try:
                await member.ban(reason="Protection anti-raid: compte trop récent")
                if config["LOG_CHANNEL_ID"]:
                    channel = bot.get_channel(config["LOG_CHANNEL_ID"])
                    if channel:
                        embed = discord.Embed(title="🛡️ Anti-raid", description=f"{member.mention} banni (compte récent)", color=0xff0000)
                        await channel.send(embed=embed)
            except Exception as e:
                logging.error(f"Erreur anti-raid: {str(e)}")

@bot.event
async def on_member_remove(member):
    config = get_guild_config(member.guild.id)
    
    if config["LOG_CHANNEL_ID"]:
        channel = bot.get_channel(config["LOG_CHANNEL_ID"])
        if channel:
            embed = discord.Embed(title="👋 Membre parti", description=f"{member.name} a quitté", color=0xffa500)
            await channel.send(embed=embed)

# DÉMARRAGE (adapté pour Google Cloud VM)
if __name__ == "__main__":
    # Récupération du token depuis les variables d'environnement
    token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not token:
        logging.error("❌ Token manquant! Définissez la variable d'environnement DISCORD_BOT_TOKEN")
    else:
        # Création du dossier de configurations si inexistant
        os.makedirs('configs', exist_ok=True)
        
        # Démarrer le bot
        try:
            bot.run(token)
        except Exception as e:
            logging.error(f"Erreur lors du démarrage du bot: {str(e)}")