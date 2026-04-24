/**
 * Pinecone Index Setup Script
 * Run this once to create the roblox-games index
 */

import {Pinecone} from "@pinecone-database/pinecone";
import * as dotenv from "dotenv";
import * as path from "path";

// Load environment variables
dotenv.config({path: path.join(__dirname, "../.env")});

async function setupPinecone() {
  console.log("🚀 Starting Pinecone setup...");

  const apiKey = process.env.PINECONE_API_KEY;
  if (!apiKey) {
    console.error("❌ PINECONE_API_KEY not found in .env file");
    process.exit(1);
  }

  const pc = new Pinecone({apiKey});

  try {
    // Check if index already exists
    const indexes = await pc.listIndexes();
    const indexExists = indexes.indexes?.some((idx) => idx.name === "roblox-games");

    if (indexExists) {
      console.log("✅ Index 'roblox-games' already exists!");

      // Get index stats
      const index = pc.index("roblox-games");
      const stats = await index.describeIndexStats();
      console.log("📊 Index Stats:", stats);
    } else {
      console.log("📝 Creating index 'roblox-games'...");

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

      console.log("✅ Index 'roblox-games' created successfully!");
      console.log("⏳ Waiting for index to be ready (this may take a minute)...");

      // Wait for index to be ready
      let ready = false;
      while (!ready) {
        const indexList = await pc.listIndexes();
        const targetIndex = indexList.indexes?.find((idx) => idx.name === "roblox-games");
        if (targetIndex?.status?.ready) {
          ready = true;
        } else {
          await new Promise((resolve) => setTimeout(resolve, 5000));
          console.log("⏳ Still waiting...");
        }
      }

      console.log("✅ Index is ready!");
    }

    console.log("\n🎉 Pinecone setup complete!");
    console.log("\nNext steps:");
    console.log("1. Deploy your Cloud Functions: firebase deploy --only functions");
    console.log("2. Test crawlGames to fetch Roblox games");
    console.log("3. Test generateEmbeddings to create vectors");
    console.log("4. Start using the recommendation engine!");
  } catch (error) {
    console.error("❌ Error setting up Pinecone:", error);
    process.exit(1);
  }
}

setupPinecone();
