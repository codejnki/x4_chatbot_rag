import os
import ssl
import discord
import httpx
from openai import OpenAI, APIError
import asyncio
import logging
import tiktoken
import config as CONFIG
from logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

# Replace with your actual bot token
TOKEN = os.getenv('X4_WIKI_DISCORD_BOT_TOKEN')
OPENAPI_ENDPOINT = 'https://192.168.190.106:8001/v1'  # Replace with your OpenAPI endpoint
TOKENIZER = tiktoken.get_encoding("cl100k_base")
MAX_CONTEXT_TOKENS = 15750
PRIVATE_CA_CERT_PATH = "rootCA.pem"

if not os.path.exists(PRIVATE_CA_CERT_PATH):
    raise FileNotFoundError(f"The CA was not found at: {PRIVATE_CA_CERT_PATH}")

ssl_ctx = ssl.create_default_context(cafile=PRIVATE_CA_CERT_PATH)
custom_httpx_client = httpx.Client(verify=ssl_ctx)


LLM_CLIENT = OpenAI(base_url=OPENAPI_ENDPOINT, api_key="", http_client=custom_httpx_client)



class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.session = None  # Initialize aiohttp session

    async def on_connect(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')


    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        if '!betty' in message.content.lower():
            logger.debug(f'Received Betty command from {message.author}')
            try:
                # Stripping the first 7 to not pass in !betty
                response = call_llm(prompt=message.content[7:], context_for_logging="")
                if response:
                    await message.channel.send(f"{response}")
                else:
                    await message.channel.send("OpenAPI Error")
            except APIError as e:
                logger.error(f"Error calling OpenAPI: {e}")
                await message.channel.send("Error calling OpenAPI service.")

def call_llm(prompt: str, context_for_logging: str) -> str:
    """Generic LLM call function with error handling."""
    try:
        prompt_tokens = len(TOKENIZER.encode(prompt))
        if prompt_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(f"Prompt for context '{context_for_logging}' is too large ({prompt_tokens} tokens).")
            return ""
        
        response = LLM_CLIENT.chat.completions.create(
            model=CONFIG.SUMMARY_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip() # type: ignore
    except APIError as e:
        logger.error(f"API error for context '{context_for_logging}': {e}")
        return ""
    except Exception as e:
        logger.error(f"An unexpected error occurred for context '{context_for_logging}': {e}")
        return ""

async def main():
    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    try:
        await client.start(TOKEN)
    except discord.LoginFailure:
        logger.error("Improper token has been passed.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
