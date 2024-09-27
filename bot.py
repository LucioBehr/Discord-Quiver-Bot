import discord
from discord.ext import commands
import asyncio
from datetime import datetime, time
import pytz
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def is_valid_wallet_address(address):
    # Implement wallet address validation here
    return len(address) == 42 and address.startswith("0x")  # Example validation for Ethereum addresses

def is_within_working_hours():
    utc_now = datetime.now(pytz.UTC)
    current_time = utc_now.time()
    weekday = utc_now.weekday()
    
    if weekday < 5:  # Monday to Friday
        start_time = time(14, 0)  # 2 PM UTC
        end_time = time(22, 0)    # 10 PM UTC
    else:  # Saturday and Sunday
        start_time = time(16, 0)  # 4 PM UTC
        end_time = time(20, 0)    # 8 PM UTC
    
    return start_time <= current_time <= end_time

@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel) and channel.name.lower().startswith('ticket-'):
        if channel.category and channel.category.name.lower() == 'support':
            await asyncio.sleep(1)  # Wait 1 second before sending the message
            await send_ticket_options(channel)

async def send_ticket_options(channel):
    view = TicketView(channel)
    await channel.send("Please select the type of ticket:", view=view)

class TicketView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary)
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()  # Delete the message asking for ticket type
        
        # Send a new message to the channel instead of a followup
        await self.channel.send("Support ticket confirmed. Please provide your wallet address:")
        
        def check(m):
            return m.channel == self.channel and m.author == interaction.user

        wallet_msg = await bot.wait_for('message', check=check)
        if is_valid_wallet_address(wallet_msg.content):
            await self.ask_support_type(interaction.channel)
        else:
            view = InvalidWalletView(self.channel)
            await self.channel.send("Invalid wallet address. Would you like to try again or proceed without providing a wallet address?", view=view)

    @discord.ui.button(label="Marketing", style=discord.ButtonStyle.secondary)
    async def marketing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()  # Delete the message asking for ticket type
        
        marketing_category = discord.utils.get(interaction.guild.categories, name="marketing_tickets")
        if marketing_category:
            await self.channel.edit(category=marketing_category)
            await self.channel.send("Ticket transferred to the Marketing category.")
        else:
            await self.channel.send("Marketing category not found. Please create it first.")

    async def ask_support_type(self, channel):
        support_options = ["Deposit", "Withdraw", "Trades", "Visual Bugs", "Others"]
        options = [discord.SelectOption(label=option, value=option.lower()) for option in support_options]
        
        select = discord.ui.Select(placeholder="Select the type of support", options=options)
        
        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await interaction.message.delete()  # Delete the message asking for support type
            await channel.send(f"You selected: {select.values[0]}. Please describe the issue you're experiencing.")
            
            def check(m):
                return m.channel == self.channel and m.author == interaction.user

            description_msg = await bot.wait_for('message', check=check)
            await self.send_working_hours_message(channel)

        select.callback = select_callback
        view = discord.ui.View(timeout=None)
        view.add_item(select)
        await channel.send("Please select the type of support you need:", view=view)

    async def send_working_hours_message(self, channel):
        utc_now = datetime.now(pytz.UTC)
        is_weekend = utc_now.weekday() >= 5

        if is_within_working_hours():
            if is_weekend:
                working_hours_msg = (
                    "We are currently within our operating hours. A member of our team will respond to you as soon as possible. "
                    "Please note that as it is the weekend, response times may be slightly longer than usual."
                )
            else:
                working_hours_msg = "We are currently within our operating hours. A member of our team will respond to you as soon as possible."
        else:
            working_hours_msg = (
                "We are currently outside of our operating hours. We will respond to your inquiry as soon as possible during our next operational period.\n\n"
                "Our operating hours are as follows:\n"
                "• Monday: 2 PM UTC - 10 PM UTC\n"
                "• Tuesday: 2 PM UTC - 10 PM UTC\n"
                "• Wednesday: 2 PM UTC - 10 PM UTC\n"
                "• Thursday: 2 PM UTC - 10 PM UTC\n"
                "• Friday: 2 PM UTC - 10 PM UTC\n"
                "• Saturday: 4 PM UTC - 8 PM UTC\n"
                "• Sunday: 4 PM UTC - 8 PM UTC\n\n"
                "Please note that response times may be slightly longer during weekends."
            )

        await channel.send(working_hours_msg)

class InvalidWalletView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.primary)
    async def try_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()
        await self.channel.send("Please provide your wallet address:")
        
        def check(m):
            return m.channel == self.channel and m.author == interaction.user

        wallet_msg = await bot.wait_for('message', check=check)
        if is_valid_wallet_address(wallet_msg.content):
            await TicketView(self.channel).ask_support_type(self.channel)
        else:
            new_view = InvalidWalletView(self.channel)
            await self.channel.send("Invalid wallet address. Would you like to try again or proceed without providing a wallet address?", view=new_view)

    @discord.ui.button(label="Proceed Without Wallet", style=discord.ButtonStyle.secondary)
    async def proceed_without_wallet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()
        await TicketView(self.channel).ask_support_type(self.channel)

class CloseTicketView(discord.ui.View):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()
        
        # Move the channel to the "WAITING-CLOSE" category
        waiting_close_category = discord.utils.get(interaction.guild.categories, name="WAITING-CLOSE")
        if waiting_close_category:
            await self.channel.edit(category=waiting_close_category)
        else:
            await self.channel.send("WAITING-CLOSE category not found. Please create it first.")
        
        # Send the thank you message
        await self.channel.send("Thank you for using our support.")

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.message.delete()
        await self.channel.send("The ticket will remain open. What issue are you still experiencing?")

@bot.command()
async def close(ctx):
    if not any(role.name.lower() == 'team member' for role in ctx.author.roles):
        await ctx.send("You don't have permission to use this command.")
        return

    try:
        await ctx.message.delete()
    except discord.errors.Forbidden:
        pass  # If the bot can't delete the message, we'll just ignore this step

    view = CloseTicketView(ctx.channel)
    await ctx.send("Have all issues been resolved? Can this ticket be closed?", view=view)

bot.run(TOKEN)
