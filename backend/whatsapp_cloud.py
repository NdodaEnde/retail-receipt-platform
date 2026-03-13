"""
WhatsApp Cloud API Integration (Official Meta API)
Handles sending and receiving messages via WhatsApp Business Platform
"""

import os
import logging
import httpx
import json
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Default verify token (can be overridden by env var)
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'retail_rewards_webhook_2026')


class WhatsAppCloudAPI:
    """
    WhatsApp Cloud API client for sending messages and handling webhooks
    """
    
    def __init__(self):
        # Load config lazily at initialization time (after .env is loaded)
        self.phone_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
        self.access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
        self.api_version = os.environ.get('WHATSAPP_API_VERSION', 'v23.0')
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        
        if not self.access_token or self.access_token == 'YOUR_ACCESS_TOKEN_HERE':
            logger.warning("⚠️ WhatsApp access token not configured")
        else:
            logger.info(f"✅ WhatsApp Cloud API initialized (Phone ID: {self.phone_number_id})")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def send_text_message(self, to: str, message: str) -> Dict[str, Any]:
        """
        Send a text message via WhatsApp
        
        Args:
            to: Recipient phone number (format: 27769695462, no +)
            message: Text message to send
        """
        # Remove + if present
        to = to.replace('+', '').strip()
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Message sent to {to}")
                    return {"success": True, "response": response.json()}
                else:
                    logger.error(f"❌ Failed to send message: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            logger.error(f"❌ WhatsApp API error: {e}")
            return {"success": False, "error": str(e)}

    async def send_reply(self, to: str, message: str, message_id: str) -> Dict[str, Any]:
        """Send a reply to a specific message"""
        to = to.replace('+', '').strip()
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "context": {"message_id": message_id},
            "text": {"body": message}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )
                return {"success": response.status_code == 200, "response": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_location_request(self, to: str, message: str) -> Dict[str, Any]:
        """Send a location request button via WhatsApp interactive message"""
        to = to.replace('+', '').strip()

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "location_request_message",
                "body": {"text": message},
                "action": {"name": "send_location"}
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )
                if response.status_code == 200:
                    logger.info(f"✅ Location request sent to {to}")
                    return {"success": True, "response": response.json()}
                else:
                    logger.error(f"❌ Failed to send location request: {response.text}")
                    return {"success": False, "error": response.text}
        except Exception as e:
            logger.error(f"❌ Location request error: {e}")
            return {"success": False, "error": str(e)}

    async def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to mark as read: {e}")
            return False

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Download media file (image) from WhatsApp
        
        Args:
            media_id: The media ID from the webhook
            
        Returns:
            Image bytes or None if failed
        """
        try:
            # Step 1: Get media URL
            async with httpx.AsyncClient() as client:
                url_response = await client.get(
                    f"https://graph.facebook.com/{self.api_version}/{media_id}",
                    headers=self._get_headers(),
                    timeout=30
                )
                
                if url_response.status_code != 200:
                    logger.error(f"Failed to get media URL: {url_response.text}")
                    return None
                
                media_url = url_response.json().get('url')
                
                if not media_url:
                    logger.error("No media URL in response")
                    return None
                
                # Step 2: Download the actual media
                media_response = await client.get(
                    media_url,
                    headers=self._get_headers(),
                    timeout=60
                )
                
                if media_response.status_code == 200:
                    logger.info(f"✅ Downloaded media {media_id}")
                    return media_response.content
                else:
                    logger.error(f"Failed to download media: {media_response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Media download error: {e}")
            return None

    async def send_winner_notification(self, to: str, prize_amount: float, draw_date: str, total_entries: int = 0) -> Dict[str, Any]:
        """Send winner notification message"""
        entries_line = f"\n🌟 _You beat {total_entries - 1} other entries!_ 🌟\n" if total_entries > 1 else ""
        message = (
            f"🎉🎊🥳 *CONGRATULATIONS!* 🥳🎊🎉\n\n"
            f"🏆🏆🏆🏆🏆🏆🏆🏆🏆🏆\n\n"
            f"*YOU ARE TODAY'S WINNER!* 🎯\n\n"
            f"💰💰 *Prize: R{prize_amount:.2f}* 💰💰\n"
            f"📅 Draw Date: {draw_date}\n"
            f"{entries_line}\n"
            f"🎁 Your purchase has been refunded! 🎁\n\n"
            f"Keep shopping and uploading receipts\n"
            f"for more chances to win! 🎰🍀\n\n"
            f"🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊"
        )
        return await self.send_text_message(to, message)

    async def send_receipt_confirmation(
        self,
        to: str,
        shop_name: str,
        amount: float,
        items_count: int,
        fraud_flag: str,
        portal_url: str = None
    ) -> Dict[str, Any]:
        """Send receipt processing confirmation"""

        if fraud_flag == "valid":
            status_msg = "✅ You're entered in today's draw! Good luck!"
        elif fraud_flag == "review":
            status_msg = "⏳ Your receipt is being reviewed. We'll notify you once approved."
        else:
            status_msg = "⚠️ Your receipt needs verification. Our team will review it."

        portal_line = f"\n📊 Your spending report: {portal_url}" if portal_url else ""

        message = (
            f"📸 *Receipt Processed!*\n\n"
            f"🏪 Shop: {shop_name or 'Detected'}\n"
            f"💰 Amount: R{amount:.2f}\n"
            f"📦 Items: {items_count}\n\n"
            f"{status_msg}\n\n"
            f"🎰 Daily draw at 21:00 SAST!"
            f"{portal_line}"
        )
        return await self.send_text_message(to, message)

    async def send_welcome_message(self, to: str) -> Dict[str, Any]:
        """Send welcome/help message"""
        message = (
            "🎰 *Welcome to Retail Rewards SA!*\n\n"
            "Win back what you spend at SA retailers!\n\n"
            "*How it works:*\n"
            "1️⃣ Shop at any SA retailer\n"
            "2️⃣ Send us a photo of your receipt\n"
            "3️⃣ Share your location 📍\n"
            "4️⃣ Enter the daily draw automatically!\n\n"
            "*Commands:*\n"
            "• RECEIPTS - View your uploads\n"
            "• WINS - Check your winnings\n"
            "• STATUS - Today's draw info\n"
            "• BALANCE - Your total stats\n"
            "• REPORT - Your spending report 📊\n\n"
            "🏆 One lucky winner daily wins back their spend!\n\n"
            "_Send a receipt photo to get started!_"
        )
        return await self.send_text_message(to, message)


def parse_webhook_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse incoming webhook message from WhatsApp Cloud API
    
    Returns:
        Dict with: phone_number, message_type, message_id, content, media_id, location
    """
    try:
        entry = body.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        
        # Check if this is a message
        messages = value.get('messages', [])
        if not messages:
            return None
        
        message = messages[0]
        contacts = value.get('contacts', [{}])
        
        # Extract phone number (remove 'whatsapp:' prefix if present)
        phone = message.get('from', '')
        
        # Get message type and content
        msg_type = message.get('type', 'text')
        msg_id = message.get('id', '')
        
        result = {
            "phone_number": phone,
            "message_type": msg_type,
            "message_id": msg_id,
            "content": None,
            "media_id": None,
            "mime_type": None,
            "location": None,
            "contact_name": contacts[0].get('profile', {}).get('name') if contacts else None,
            "timestamp": message.get('timestamp')
        }
        
        # Parse based on message type
        if msg_type == 'text':
            result["content"] = message.get('text', {}).get('body', '')
            
        elif msg_type == 'image':
            image_data = message.get('image', {})
            result["media_id"] = image_data.get('id')
            result["mime_type"] = image_data.get('mime_type', 'image/jpeg')
            result["content"] = image_data.get('caption', '')
            
        elif msg_type == 'document':
            doc_data = message.get('document', {})
            result["media_id"] = doc_data.get('id')
            result["mime_type"] = doc_data.get('mime_type')
            result["content"] = doc_data.get('filename', '')
            
        elif msg_type == 'location':
            loc_data = message.get('location', {})
            result["location"] = {
                "latitude": loc_data.get('latitude'),
                "longitude": loc_data.get('longitude'),
                "name": loc_data.get('name'),
                "address": loc_data.get('address')
            }
            
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse webhook: {e}")
        return None


# Singleton instance
_whatsapp_client = None

def get_whatsapp_client() -> WhatsAppCloudAPI:
    """Get or create WhatsApp client singleton"""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppCloudAPI()
    return _whatsapp_client
