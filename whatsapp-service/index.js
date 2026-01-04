const { makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const QRCode = require('qrcode');
const pino = require('pino');

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Configuration
const FASTAPI_URL = process.env.FASTAPI_URL || 'http://localhost:8001';
const PORT = process.env.PORT || 3001;
const AUTH_DIR = path.join(__dirname, 'auth_info');

// Ensure auth directory exists
if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
}

// Logger
const logger = pino({ level: 'info' });

// State
let sock = null;
let qrCode = null;
let connectionStatus = 'disconnected';
let lastQRTimestamp = 0;

// Initialize WhatsApp Connection
async function initWhatsApp() {
    try {
        const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

        sock = makeWASocket({
            auth: state,
            printQRInTerminal: true,
            logger: pino({ level: 'silent' }),
            browser: ['Retail Rewards Bot', 'Chrome', '1.0.0'],
            getMessage: async () => undefined
        });

        // Connection updates
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                qrCode = qr;
                lastQRTimestamp = Date.now();
                connectionStatus = 'awaiting_scan';
                logger.info('QR Code generated - scan with WhatsApp');
            }

            if (connection === 'close') {
                const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
                connectionStatus = 'disconnected';
                logger.info(`Connection closed. Reconnecting: ${shouldReconnect}`);
                
                if (shouldReconnect) {
                    setTimeout(initWhatsApp, 5000);
                }
            } else if (connection === 'open') {
                connectionStatus = 'connected';
                qrCode = null;
                logger.info('WhatsApp connected successfully!');
            }
        });

        // Save credentials on update
        sock.ev.on('creds.update', saveCreds);

        // Handle incoming messages
        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type === 'notify') {
                for (const message of messages) {
                    if (!message.key.fromMe && message.message) {
                        await handleIncomingMessage(message);
                    }
                }
            }
        });

    } catch (error) {
        logger.error('WhatsApp initialization error:', error);
        connectionStatus = 'error';
        setTimeout(initWhatsApp, 10000);
    }
}

// Handle incoming messages
async function handleIncomingMessage(message) {
    try {
        const phoneNumber = message.key.remoteJid.replace('@s.whatsapp.net', '');
        const messageType = Object.keys(message.message)[0];
        
        logger.info(`Received ${messageType} from ${phoneNumber}`);

        // Extract location if available (from message or device)
        let latitude = null;
        let longitude = null;

        // Check for location message
        if (message.message.locationMessage) {
            latitude = message.message.locationMessage.degreesLatitude;
            longitude = message.message.locationMessage.degreesLongitude;
            logger.info(`Location received: ${latitude}, ${longitude}`);
        }

        // Handle image messages (receipts)
        if (messageType === 'imageMessage' || messageType === 'documentMessage') {
            await handleReceiptImage(message, phoneNumber, latitude, longitude);
            return;
        }

        // Handle text messages
        const textContent = message.message.conversation || 
                          message.message.extendedTextMessage?.text || '';
        
        await handleTextMessage(phoneNumber, textContent.toLowerCase().trim(), latitude, longitude);

    } catch (error) {
        logger.error('Error handling message:', error);
    }
}

// Handle receipt image upload
async function handleReceiptImage(message, phoneNumber, latitude, longitude) {
    try {
        // Send acknowledgment
        await sendMessage(phoneNumber, '📸 Receipt received! Processing with AI...');

        // Download the image
        const buffer = await downloadMediaMessage(message, 'buffer', {});
        const base64Image = buffer.toString('base64');

        // Get image mime type
        const imageMsg = message.message.imageMessage || message.message.documentMessage;
        const mimeType = imageMsg?.mimetype || 'image/jpeg';

        // Send to FastAPI for processing with LandingAI
        const response = await axios.post(`${FASTAPI_URL}/api/receipts/process-image`, {
            phone_number: phoneNumber,
            image_data: base64Image,
            mime_type: mimeType,
            latitude: latitude,
            longitude: longitude
        }, {
            timeout: 60000 // 60 second timeout for AI processing
        });

        if (response.data.success) {
            const receipt = response.data.receipt;
            const shopName = receipt.shop_name || 'Unknown Shop';
            const amount = receipt.amount?.toFixed(2) || '0.00';
            const items = receipt.items?.length || 0;

            let replyMsg = `✅ Receipt processed successfully!\n\n`;
            replyMsg += `🏪 Shop: ${shopName}\n`;
            replyMsg += `💰 Amount: $${amount}\n`;
            replyMsg += `📦 Items: ${items}\n`;
            
            if (latitude && longitude) {
                replyMsg += `📍 Location captured\n`;
            }
            
            replyMsg += `\n🎰 You're entered in today's draw! Good luck!`;

            await sendMessage(phoneNumber, replyMsg);
        } else {
            await sendMessage(phoneNumber, 
                `❌ Could not process receipt: ${response.data.error || 'Unknown error'}\n\nPlease try again with a clearer photo.`
            );
        }

    } catch (error) {
        logger.error('Error processing receipt image:', error.message);
        await sendMessage(phoneNumber, 
            '❌ Error processing your receipt. Please try again or contact support.'
        );
    }
}

// Handle text commands
async function handleTextMessage(phoneNumber, text, latitude, longitude) {
    let reply = '';

    // Store location if shared
    if (latitude && longitude) {
        try {
            await axios.post(`${FASTAPI_URL}/api/customers/location`, {
                phone_number: phoneNumber,
                latitude,
                longitude
            });
        } catch (e) {
            logger.error('Failed to store location:', e.message);
        }
    }

    switch (true) {
        case ['hi', 'hello', 'hey', 'start', 'help', '?'].includes(text):
            reply = `🎰 *Welcome to Retail Rewards!*\n\n` +
                   `📸 *Send a receipt photo* to enter today's draw\n` +
                   `📍 *Share your location* first for better tracking\n\n` +
                   `*Commands:*\n` +
                   `• RECEIPTS - View your recent receipts\n` +
                   `• WINS - Check your winnings\n` +
                   `• STATUS - Today's draw status\n` +
                   `• BALANCE - Your total stats\n\n` +
                   `🏆 Daily draw at midnight - win back your spend!`;
            break;

        case text === 'receipts':
            reply = await getCustomerReceipts(phoneNumber);
            break;

        case text === 'wins':
            reply = await getCustomerWins(phoneNumber);
            break;

        case text === 'status':
            reply = await getDrawStatus(phoneNumber);
            break;

        case text === 'balance':
            reply = await getCustomerBalance(phoneNumber);
            break;

        default:
            reply = `I didn't understand that. Send *HELP* for available commands.\n\n` +
                   `💡 Tip: Send a receipt photo to enter today's draw!`;
    }

    await sendMessage(phoneNumber, reply);
}

// API helper functions
async function getCustomerReceipts(phoneNumber) {
    try {
        const response = await axios.get(`${FASTAPI_URL}/api/receipts/customer/${phoneNumber}?limit=5`);
        const receipts = response.data.receipts;
        
        if (!receipts || receipts.length === 0) {
            return '📋 No receipts yet.\n\nSend a receipt photo to get started!';
        }

        let msg = `📋 *Your Recent Receipts (${response.data.total} total)*\n\n`;
        receipts.forEach((r, i) => {
            const status = r.status === 'won' ? '🏆' : '✅';
            const date = new Date(r.created_at).toLocaleDateString();
            msg += `${i + 1}. ${status} ${r.shop_name || 'Unknown'} - $${r.amount?.toFixed(2) || '0.00'}\n   📅 ${date}\n`;
        });

        return msg;
    } catch (error) {
        return '❌ Error fetching receipts. Please try again.';
    }
}

async function getCustomerWins(phoneNumber) {
    try {
        const response = await axios.get(`${FASTAPI_URL}/api/draws/winner/${phoneNumber}`);
        const wins = response.data.wins;

        if (!wins || wins.length === 0) {
            return '🏆 No wins yet.\n\nKeep uploading receipts for a chance to win!';
        }

        const totalWon = wins.reduce((sum, w) => sum + (w.prize_amount || 0), 0);
        let msg = `🏆 *Your Wins!*\n\n`;
        msg += `💰 Total Won: *$${totalWon.toFixed(2)}*\n\n`;
        
        wins.slice(0, 5).forEach(w => {
            msg += `• ${w.draw_date}: $${w.prize_amount?.toFixed(2)}\n`;
        });

        return msg;
    } catch (error) {
        return '❌ Error fetching wins. Please try again.';
    }
}

async function getDrawStatus(phoneNumber) {
    try {
        const today = new Date().toISOString().split('T')[0];
        const response = await axios.get(`${FASTAPI_URL}/api/draws/${today}`);
        const draw = response.data;

        if (draw && draw.status === 'completed') {
            if (draw.winner_customer_phone === phoneNumber) {
                return `🎉 *YOU WON TODAY!*\n\n💰 Prize: *$${draw.prize_amount?.toFixed(2)}*\n\nCongratulations! 🎊`;
            }
            return `📊 *Today's Draw Complete*\n\n` +
                   `🎟️ Total Entries: ${draw.total_receipts}\n` +
                   `💰 Prize Pool: $${draw.total_amount?.toFixed(2)}\n` +
                   `🏆 Winner notified!\n\n` +
                   `Keep uploading receipts for tomorrow's draw!`;
        }

        // Get today's receipt count
        const receiptsRes = await axios.get(`${FASTAPI_URL}/api/receipts?date=${today}`);
        return `🎰 *Today's Draw Status*\n\n` +
               `🎟️ Entries so far: ${receiptsRes.data.total}\n` +
               `⏰ Draw time: Midnight UTC\n\n` +
               `Send more receipts to increase your chances!`;

    } catch (error) {
        return '❌ Error fetching draw status. Please try again.';
    }
}

async function getCustomerBalance(phoneNumber) {
    try {
        const response = await axios.get(`${FASTAPI_URL}/api/customers/${phoneNumber}`);
        const customer = response.data;

        return `📊 *Your Stats*\n\n` +
               `📋 Receipts: ${customer.total_receipts || 0}\n` +
               `💵 Total Spent: $${customer.total_spent?.toFixed(2) || '0.00'}\n` +
               `🏆 Wins: ${customer.total_wins || 0}\n` +
               `💰 Won Back: $${customer.total_winnings?.toFixed(2) || '0.00'}`;

    } catch (error) {
        return '❌ Error fetching balance. Please try again.';
    }
}

// Send message helper
async function sendMessage(phoneNumber, text) {
    try {
        if (!sock) {
            logger.error('WhatsApp not connected');
            return false;
        }

        const jid = phoneNumber.includes('@') ? phoneNumber : `${phoneNumber}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        logger.info(`Message sent to ${phoneNumber}`);
        return true;

    } catch (error) {
        logger.error('Error sending message:', error);
        return false;
    }
}

// REST API Endpoints
app.get('/health', (req, res) => {
    res.json({ status: 'ok', whatsapp: connectionStatus });
});

app.get('/qr', async (req, res) => {
    try {
        if (!qrCode) {
            return res.json({ qr: null, connected: connectionStatus === 'connected' });
        }
        
        // Generate QR code as data URL
        const qrDataUrl = await QRCode.toDataURL(qrCode);
        res.json({ 
            qr: qrDataUrl, 
            qr_raw: qrCode,
            connected: false,
            timestamp: lastQRTimestamp
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/status', (req, res) => {
    res.json({
        connected: connectionStatus === 'connected',
        status: connectionStatus,
        user: sock?.user || null
    });
});

app.post('/send', async (req, res) => {
    const { phone_number, message } = req.body;
    
    if (!phone_number || !message) {
        return res.status(400).json({ error: 'phone_number and message required' });
    }

    const success = await sendMessage(phone_number, message);
    res.json({ success });
});

// Notify winner endpoint (called by FastAPI after draw)
app.post('/notify-winner', async (req, res) => {
    const { phone_number, prize_amount, draw_date } = req.body;
    
    const message = `🎉🎊 *CONGRATULATIONS!* 🎊🎉\n\n` +
                   `You've WON today's Retail Rewards draw!\n\n` +
                   `💰 *Prize: $${prize_amount?.toFixed(2)}*\n` +
                   `📅 Draw Date: ${draw_date}\n\n` +
                   `Your purchase has been refunded! 🎁\n\n` +
                   `Share your win with friends! 🚀`;

    const success = await sendMessage(phone_number, message);
    res.json({ success });
});

// Start server
app.listen(PORT, () => {
    logger.info(`WhatsApp service running on port ${PORT}`);
    initWhatsApp();
});
