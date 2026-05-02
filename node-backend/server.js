require('dotenv').config();
const express = require('express');
const cors = require('cors');

const { connectDB, initGridFS } = require("./app/config/db.config");   // ← Fixed import path
const authRoutes = require("./app/routes/authRoutes");
const uploadRoutes = require("./app/routes/uploadRoutes");
const chatbotRoutes = require("./app/routes/chatbotRoutes");

const app = express();

app.use(express.json());
app.use(cors());

// Root health check
app.get('/', (req, res) => {
    res.json({ 
        message: "Asaan-Form Node.js Backend is running", 
        status: "ok",
        gridfs: "ready" 
    });
});

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/upload', uploadRoutes);
app.use('/api/chatbot', chatbotRoutes);

const PORT = process.env.PORT || 3000;

// Proper startup sequence
const startServer = async () => {
    try {
        // 1. Connect to MongoDB
        await connectDB();
        
        // 2. Initialize GridFS (must be AFTER DB connection)
        initGridFS();
        console.log("✅ GridFS initialized successfully");

        // 3. Start HTTP server
        const server = app.listen(PORT, () => {
            console.log(`🚀 Server is running on port ${PORT}`);
        });

        // 4. Initialize WebSocket
        const { initWebSocket } = require('./app/websocket/wsServer');
        initWebSocket(server);

        server.timeout = 600000; // 10 minutes for long AI calls

    } catch (error) {
        console.error("❌ Server startup failed:", error.message);
        process.exit(1);
    }
};

// Start the server
startServer();