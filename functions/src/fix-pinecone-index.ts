/**
 * Fix Pinecone Index Dimensions
 * Deletes and recreates the index with correct dimensions (1536)
 */

import {Pinecone} from "@pinecone-database/pinecone";
import * as dotenv from "dotenv";
import * as path from "path";

dotenv.config({path: path.join(__dirname, "../.env")});

async function fixPineconeIndex() {
  console.log("🔧 Fixing Pinecone index dimensions...");

  const apiKey = process.env.PINECONE_API_KEY;
  if (!apiKey) {
    console.error("❌ PINECONE_API_KEY not found in .env file");
    process.exit(1);
  }

  const pc = new Pinecone({apiKey});

  try {
    // Delete existing index
    console.log("🗑️  Deleting old index 'roblox-games'...");
    await pc.deleteIndex("roblox-games");

    // Wait for deletion
    console.log("⏳ Waiting for deletion to complete...");
    await new Promise((resolve) => setTimeout(resolve, 10000));

    // Create new index with correct dimensions
    console.log("📝 Creating new index with 1536 dimensions...");
    await pc.createIndex({
      name: "roblox-games",
      dimension: 1536,
      metric: "cosine",
      spec: {
        serverless: {
          cloud: "aws",
          region: "us-east-1",
        },
      },
    });

    console.log("✅ Index created successfully!");
    console.log("⏳ Waiting for index to be ready...");

    // Wait for index to be ready
    let ready = false;
    let attempts = 0;
    while (!ready && attempts < 30) {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      const indexList = await pc.listIndexes();
      const targetIndex = indexList.indexes?.find((idx) => idx.name === "roblox-games");
      if (targetIndex?.status?.ready) {
        ready = true;
      } else {
        attempts++;
        console.log(`⏳ Still waiting... (${attempts * 5}s)`);
      }
    }

    if (ready) {
      console.log("✅ Index is ready!");

      // Verify stats
      const index = pc.index("roblox-games");
      const stats = await index.describeIndexStats();
      console.log("📊 New Index Stats:", stats);
      console.log(`✅ Dimension: ${stats.dimension}`);
    } else {
      console.log("⚠️  Index creation is taking longer than expected.");
      console.log("   Check Pinecone dashboard to verify it's created.");
    }

    console.log("\n🎉 Pinecone index fixed!");
  } catch (error) {
    console.error("❌ Error fixing Pinecone index:", error);
    process.exit(1);
  }
}

fixPineconeIndex();
