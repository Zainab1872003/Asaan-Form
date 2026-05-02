const mongoose = require("mongoose");
const multer = require("multer");
require("dotenv").config();

const dbURL = process.env.dbURL;

const connectDB = async () => {
    try {
        const conn = await mongoose.connect(dbURL);
        console.log(`✅ MongoDB Connected: ${conn.connection.host}`);
        return conn;
    } catch (error) {
        console.error(`❌ MongoDB Connection Error: ${error.message}`);
        process.exit(1);
    }
};

// ==================== GRIDFS SETUP ====================
let bucket;

const initGridFS = () => {
    if (bucket) return;
    const db = mongoose.connection.db;
    bucket = new mongoose.mongo.GridFSBucket(db, {
        bucketName: "uploads"   // This is the collection name in MongoDB
    });
    console.log("✅ GridFS Bucket initialized successfully");
};

const getGridFSBucket = () => {
    if (!bucket) throw new Error("GridFS not initialized. Call initGridFS() first.");
    return bucket;
};

// Memory storage (file stays in RAM as buffer)
const storage = multer.memoryStorage();

const upload = multer({
    storage,
    limits: { fileSize: 20 * 1024 * 1024 } // 20MB limit
});

module.exports = { 
    connectDB, 
    upload, 
    initGridFS, 
    getGridFSBucket 
};