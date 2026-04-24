/**
 * Local Test Server with Mock Data
 * Runs without Firebase credentials using in-memory data
 */

import express from "express";
import * as dotenv from "dotenv";
import * as path from "path";
import cors from "cors";
import {Pinecone} from "@pinecone-database/pinecone";
import OpenAI from "openai";
import axios from "axios";

// Load environment variables
dotenv.config({path: path.join(__dirname, "../.env")});

// In-memory data stores (replacing Firestore)
const gamesDB: Map<string, any> = new Map();
const usersDB: Map<string, any> = new Map();
const feedbackDB: Map<string, Map<string, any>> = new Map();

// Initialize OpenAI
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "",
});

// Initialize Pinecone
let pineconeClient: Pinecone | null = null;
const initPinecone = () => {
  if (!pineconeClient && process.env.PINECONE_API_KEY) {
    pineconeClient = new Pinecone({
      apiKey: process.env.PINECONE_API_KEY,
    });
  }
  return pineconeClient;
};

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 5001;

// Health check
app.get("/", (req, res) => {
  res.json({
    status: "running",
    message: "Roblox Discovery Local Test Server (Mock Mode)",
    note: "Using in-memory data instead of Firestore",
    endpoints: [
      "POST /crawlGames",
      "POST /generateEmbeddings",
      "POST /submitFeedback",
      "POST /getQueue",
      "POST /resetUserProfile",
      "POST /getStats",
    ],
  });
});

// crawlGames endpoint
app.post("/crawlGames", async (req, res) => {
  try {
    console.log("🎮 Starting game crawl...");

    const {keywords, limit = 50} = req.body;

    if (!keywords || !Array.isArray(keywords)) {
      res.status(400).json({
        error: "Invalid request. Expected {keywords: string[], limit?: number}",
      });
      return;
    }

    const crawledGames: any[] = [];

    for (const keyword of keywords) {
      console.log(`  Crawling: ${keyword}`);

      try {
        const response = await axios.get(
          `https://games.roblox.com/v1/games/list`,
          {
            params: {
              "model.keyword": keyword,
              "model.sortType": 1,
              maxRows: Math.min(limit, 10),
            },
          }
        );

        const games = response.data?.games || [];

        for (const game of games) {
          const universeId = game.universeId?.toString();
          if (!universeId) continue;

          const gameData = {
            universe_id: universeId,
            title: game.name || "Unknown",
            description: game.description || "",
            creator_name: game.creator?.name || "Unknown",
            thumbnail_url: game.imageToken || "",
            visits: game.totalUpVotes || 0,
            active_players: game.playerCount || 0,
            votes_up: game.totalUpVotes || 0,
            votes_down: game.totalDownVotes || 0,
            genre: keyword,
            last_update: new Date().toISOString(),
            has_embedding: false,
          };

          gamesDB.set(universeId, gameData);
          crawledGames.push(gameData);
          console.log(`    ✓ ${gameData.title}`);
        }
      } catch (error: any) {
        console.error(`    ✗ Error with ${keyword}:`, error.message);
      }

      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    res.json({
      success: true,
      message: `Crawled ${crawledGames.length} games`,
      games: crawledGames.length,
      sample: crawledGames.slice(0, 3),
    });
  } catch (error: any) {
    console.error("Error in crawlGames:", error);
    res.status(500).json({error: error.message});
  }
});

// generateEmbeddings endpoint
app.post("/generateEmbeddings", async (req, res) => {
  try {
    console.log("🤖 Generating embeddings...");

    const pc = initPinecone();
    if (!pc) {
      res.status(500).json({error: "Pinecone not configured"});
      return;
    }

    const index = pc.index("roblox-games");

    // Get games without embeddings
    const gamesToProcess = Array.from(gamesDB.entries())
      .filter(([_, game]) => !game.has_embedding)
      .slice(0, 10);

    if (gamesToProcess.length === 0) {
      res.json({
        success: true,
        message: "No games need embeddings",
        processed: 0,
      });
      return;
    }

    const processedGames: string[] = [];

    for (const [universeId, game] of gamesToProcess) {
      try {
        const embeddingText = `Title: ${game.title}
Description: ${game.description}
Genre: ${game.genre}
Active Players: ${game.active_players}
Creator: ${game.creator_name}`;

        console.log(`  Processing: ${game.title}`);

        const embeddingResponse = await openai.embeddings.create({
          model: "text-embedding-3-small",
          input: embeddingText,
          dimensions: 1536,
        });

        const embedding = embeddingResponse.data[0].embedding;

        await index.upsert([
          {
            id: universeId,
            values: embedding,
            metadata: {
              title: game.title,
              thumbnail: game.thumbnail_url || "",
              genre: game.genre,
              visits: game.visits,
            },
          },
        ]);

        game.has_embedding = true;
        gamesDB.set(universeId, game);

        processedGames.push(universeId);
        console.log(`    ✓ Embedded`);

        await new Promise((resolve) => setTimeout(resolve, 100));
      } catch (error: any) {
        console.error(`    ✗ Error:`, error.message);
      }
    }

    res.json({
      success: true,
      message: `Generated ${processedGames.length} embeddings`,
      processed: processedGames.length,
    });
  } catch (error: any) {
    console.error("Error in generateEmbeddings:", error);
    res.status(500).json({error: error.message});
  }
});

// getQueue endpoint
app.post("/getQueue", async (req, res) => {
  try {
    console.log("📋 Getting queue...");

    const {user_id, limit = 10} = req.body;

    if (!user_id) {
      res.status(400).json({error: "Missing required field: user_id"});
      return;
    }

    const pc = initPinecone();
    if (!pc) {
      res.status(500).json({error: "Pinecone not configured"});
      return;
    }

    const userData = usersDB.get(user_id);
    const profileEmbedding = userData?.profile_embedding;

    let recommendedGames: any[] = [];

    if (!profileEmbedding || profileEmbedding.length === 0) {
      console.log("  New user - returning popular games");

      // Return popular games
      const popularGames = Array.from(gamesDB.entries())
        .filter(([_, game]) => game.has_embedding)
        .sort((a, b) => b[1].visits - a[1].visits)
        .slice(0, limit)
        .map(([id, game]) => ({
          universe_id: id,
          ...game,
        }));

      recommendedGames = popularGames;
    } else {
      console.log("  Returning personalized recommendations");

      const index = pc.index("roblox-games");
      const queryResponse = await index.query({
        vector: profileEmbedding,
        topK: limit + 10,
        includeMetadata: true,
      });

      const userFeedback = feedbackDB.get(user_id) || new Map();
      const dislikedGames = new Set<string>();
      for (const [gameId, feedback] of userFeedback.entries()) {
        if (feedback.feedback === -1) {
          dislikedGames.add(gameId);
        }
      }

      const matches = queryResponse.matches || [];
      for (const match of matches) {
        if (recommendedGames.length >= limit) break;

        const gameId = match.id;
        if (dislikedGames.has(gameId)) continue;

        const game = gamesDB.get(gameId);
        if (game) {
          recommendedGames.push({
            universe_id: gameId,
            ...game,
            score: match.score,
          });
        }
      }
    }

    console.log(`  ✓ Found ${recommendedGames.length} games`);

    res.json({
      success: true,
      games: recommendedGames,
      count: recommendedGames.length,
    });
  } catch (error: any) {
    console.error("Error in getQueue:", error);
    res.status(500).json({error: error.message});
  }
});

// submitFeedback endpoint
app.post("/submitFeedback", async (req, res) => {
  try {
    console.log("👍 Submitting feedback...");

    const {user_id, universe_id, feedback} = req.body;

    if (!user_id || !universe_id || feedback === undefined) {
      res.status(400).json({
        error: "Missing required fields: user_id, universe_id, feedback",
      });
      return;
    }

    if (![1, 0, -1].includes(feedback)) {
      res.status(400).json({
        error: "Invalid feedback value. Must be 1 (like), 0 (skip), or -1 (dislike)",
      });
      return;
    }

    // Store feedback
    if (!feedbackDB.has(user_id)) {
      feedbackDB.set(user_id, new Map());
    }
    feedbackDB.get(user_id)!.set(universe_id, {
      feedback,
      timestamp: new Date().toISOString(),
    });

    console.log(`  ✓ Saved: ${feedback === 1 ? "Like" : feedback === -1 ? "Dislike" : "Skip"}`);

    if (feedback === 1) {
      const pc = initPinecone();
      if (pc) {
        const index = pc.index("roblox-games");

        try {
          const gameVector = await index.fetch([universe_id]);
          const gameEmbedding = gameVector.records[universe_id]?.values;

          if (gameEmbedding) {
            // Get all liked games
            const userFeedback = feedbackDB.get(user_id)!;
            const likedGames: string[] = [];
            for (const [gameId, fb] of userFeedback.entries()) {
              if (fb.feedback === 1) {
                likedGames.push(gameId);
              }
            }

            const likedEmbeddings: number[][] = [];
            for (const gameId of likedGames) {
              try {
                const vec = await index.fetch([gameId]);
                const embedding = vec.records[gameId]?.values;
                if (embedding) {
                  likedEmbeddings.push(embedding as number[]);
                }
              } catch (err) {
                // Skip
              }
            }

            if (likedEmbeddings.length > 0) {
              const avgEmbedding = likedEmbeddings[0].map((_, i) =>
                likedEmbeddings.reduce((sum, emb) => sum + emb[i], 0) / likedEmbeddings.length
              );

              usersDB.set(user_id, {
                profile_embedding: avgEmbedding,
                updated_at: new Date().toISOString(),
              });

              console.log(`  ✓ Updated profile embedding`);
            }
          }
        } catch (error: any) {
          console.error("  ✗ Error updating profile:", error.message);
        }
      }
    }

    res.json({
      success: true,
      message: "Feedback submitted successfully",
    });
  } catch (error: any) {
    console.error("Error in submitFeedback:", error);
    res.status(500).json({error: error.message});
  }
});

// getStats endpoint
app.post("/getStats", async (req, res) => {
  try {
    const gamesWithEmbeddings = Array.from(gamesDB.values()).filter(
      (game) => game.has_embedding === true
    ).length;

    res.json({
      success: true,
      stats: {
        total_games: gamesDB.size,
        games_with_embeddings: gamesWithEmbeddings,
        total_users: usersDB.size,
      },
    });
  } catch (error: any) {
    console.error("Error in getStats:", error);
    res.status(500).json({error: error.message});
  }
});

// resetUserProfile endpoint
app.post("/resetUserProfile", async (req, res) => {
  try {
    const {user_id} = req.body;

    if (!user_id) {
      res.status(400).json({error: "Missing required field: user_id"});
      return;
    }

    feedbackDB.delete(user_id);
    usersDB.set(user_id, {
      profile_embedding: [],
      updated_at: new Date().toISOString(),
    });

    res.json({
      success: true,
      message: "User profile reset successfully",
    });
  } catch (error: any) {
    console.error("Error in resetUserProfile:", error);
    res.status(500).json({error: error.message});
  }
});

app.listen(PORT, () => {
  console.log("\n🚀 Roblox Discovery Local Test Server (Mock Mode)");
  console.log(`📍 Running on http://localhost:${PORT}`);
  console.log("\n⚠️  Using in-memory data (not Firestore)");
  console.log("   Data will be lost when server restarts");
  console.log("\n✅ API Keys:");
  console.log(`   OpenAI: ${process.env.OPENAI_API_KEY ? "✓ Configured" : "✗ Missing"}`);
  console.log(`   Pinecone: ${process.env.PINECONE_API_KEY ? "✓ Configured" : "✗ Missing"}`);
  console.log("\n📋 Available Endpoints:");
  console.log("   POST http://localhost:5001/crawlGames");
  console.log("   POST http://localhost:5001/generateEmbeddings");
  console.log("   POST http://localhost:5001/submitFeedback");
  console.log("   POST http://localhost:5001/getQueue");
  console.log("   POST http://localhost:5001/resetUserProfile");
  console.log("   POST http://localhost:5001/getStats");
  console.log("\n🔗 Test: http://localhost:5001/\n");
});
