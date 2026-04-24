/**
 * Roblox Discovery App - Cloud Functions
 * Firebase + Pinecone + OpenAI Implementation
 */

import {setGlobalOptions} from "firebase-functions/v2";
import {onRequest} from "firebase-functions/v2/https";
import * as logger from "firebase-functions/logger";
import * as admin from "firebase-admin";
import {Pinecone} from "@pinecone-database/pinecone";
import OpenAI from "openai";
import axios from "axios";

// Initialize Firebase Admin
admin.initializeApp();
const db = admin.firestore();

// Set global options
setGlobalOptions({
  maxInstances: 10,
  region: "us-central1",
});

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

/**
 * Cloud Function 1: Crawl Roblox Games
 * Fetches game metadata from Roblox APIs and stores in Firestore
 */
export const crawlGames = onRequest(
  {cors: true},
  async (req, res) => {
    try {
      logger.info("Starting game crawl", {body: req.body});

      const {keywords, limit = 50} = req.body;

      if (!keywords || !Array.isArray(keywords)) {
        res.status(400).json({
          error: "Invalid request. Expected {keywords: string[], limit?: number}",
        });
        return;
      }

      const crawledGames: any[] = [];

      for (const keyword of keywords) {
        logger.info(`Crawling games for keyword: ${keyword}`);

        try {
          // Roblox catalog search for experiences (Games category)
          const response = await axios.get(
            `https://catalog.roblox.com/v1/search/items`,
            {
              params: {
                category: "Games",
                keyword: keyword,
                // Allowed limits: 10, 28, 30, 50, 60, 100, 120
                limit: Math.min(Math.max(limit, 10), 120),
                sortType: "Relevance",
              },
            }
          );

          const catalogItems = response.data?.data || [];

          // Collect universe ids (catalog id corresponds to universe id for games)
          const universeIds = catalogItems
            .map((item: any) => item.id)
            .filter(Boolean)
            .map((id: any) => id.toString());

          if (universeIds.length === 0) {
            logger.info(`No universe ids returned for keyword: ${keyword}`);
            continue;
          }

          // Fetch detailed game info in batches
          const chunkSize = 30;
          for (let i = 0; i < universeIds.length; i += chunkSize) {
            const chunk = universeIds.slice(i, i + chunkSize);

            // Fetch detailed game info
            try {
              const detailsResponse = await axios.get(
                `https://games.roblox.com/v1/games`,
                {params: {universeIds: chunk.join(",")}}
              );

              const detailedGames: any[] = detailsResponse.data?.data || [];

              for (const game of detailedGames) {
                const universeId = game.id?.toString();
                if (!universeId) continue;

                const gameData = {
                  universe_id: universeId,
                  title: game.name || "Unknown",
                  description: game.description || "",
                  creator_name: game.creator?.name || "Unknown",
                  thumbnail_url: "", // Could be enriched with thumbnails API if needed
                  visits: game.visits || 0,
                  active_players: game.playing || 0,
                  votes_up: game.favoritedCount || 0,
                  votes_down: 0,
                  genre: game.genre || keyword,
                  last_update: admin.firestore.FieldValue.serverTimestamp(),
                  has_embedding: false,
                };

                // Save to Firestore
                await db.collection("games").doc(universeId).set(gameData, {merge: true});
                crawledGames.push(gameData);

                logger.info(`Saved game: ${gameData.title} (${universeId})`);
              }

              // Rate limit between detail batches
              await new Promise((resolve) => setTimeout(resolve, 200));
            } catch (err) {
              logger.warn(`Failed to fetch details for chunk starting with ${chunk[0]}`, err);
            }
          }
        } catch (error) {
          logger.error(`Error crawling keyword ${keyword}:`, error);
        }

        // Rate limiting
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }

      res.json({
        success: true,
        message: `Crawled ${crawledGames.length} games`,
        games: crawledGames.length,
        games_stored: crawledGames.length,
      });
    } catch (error) {
      logger.error("Error in crawlGames:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);

/**
 * Cloud Function 2: Generate Embeddings
 * Creates OpenAI embeddings for games and stores in Pinecone
 */
export const generateEmbeddings = onRequest(
  {cors: true, timeoutSeconds: 540},
  async (req, res) => {
    try {
      logger.info("Starting embedding generation");

      const pc = initPinecone();
      if (!pc) {
        res.status(500).json({error: "Pinecone not configured"});
        return;
      }

      const index = pc.index("roblox-games");

      // Get all games without embeddings
      const gamesSnapshot = await db
        .collection("games")
        .where("has_embedding", "==", false)
        .limit(100)
        .get();

      if (gamesSnapshot.empty) {
        res.json({
          success: true,
          message: "No games need embeddings",
          processed: 0,
        });
        return;
      }

      const processedGames: string[] = [];

      for (const doc of gamesSnapshot.docs) {
        const game = doc.data();
        const universeId = doc.id;

        try {
          // Build embedding text
          const embeddingText = `Title: ${game.title}
Description: ${game.description}
Genre: ${game.genre}
Active Players: ${game.active_players}
Creator: ${game.creator_name}`;

          // Generate embedding
          const embeddingResponse = await openai.embeddings.create({
            model: "text-embedding-3-small",
            input: embeddingText,
            dimensions: 1536,
          });

          const embedding = embeddingResponse.data[0].embedding;

          // Upsert to Pinecone
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

          // Update Firestore
          await db.collection("games").doc(universeId).update({
            has_embedding: true,
            last_update: admin.firestore.FieldValue.serverTimestamp(),
          });

          processedGames.push(universeId);
          logger.info(`Generated embedding for: ${game.title}`);

          // Rate limiting for OpenAI
          await new Promise((resolve) => setTimeout(resolve, 100));
        } catch (error) {
          logger.error(`Error processing ${universeId}:`, error);
        }
      }

      res.json({
        success: true,
        message: `Generated ${processedGames.length} embeddings`,
        processed: processedGames.length,
      });
    } catch (error) {
      logger.error("Error in generateEmbeddings:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);

/**
 * Cloud Function 3: Submit User Feedback
 * Records user like/dislike/skip and updates profile embedding
 */
export const submitFeedback = onRequest(
  {cors: true},
  async (req, res) => {
    try {
      logger.info("Submitting feedback", {body: req.body});

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

      // Save feedback to Firestore
      await db
        .collection("users")
        .doc(user_id)
        .collection("feedback")
        .doc(universe_id)
        .set({
          feedback,
          timestamp: admin.firestore.FieldValue.serverTimestamp(),
        });

      logger.info(`Saved feedback: user=${user_id}, game=${universe_id}, feedback=${feedback}`);

      // If it's a like, update user profile embedding
      if (feedback === 1) {
        const pc = initPinecone();
        if (pc) {
          try {
            const index = pc.index("roblox-games");

            // Fetch the game embedding from Pinecone
            const gameVector = await index.fetch([universe_id]);
            const gameEmbedding = gameVector.records[universe_id]?.values;

            if (gameEmbedding) {
              // Get all liked games for this user
              const likesSnapshot = await db
                .collection("users")
                .doc(user_id)
                .collection("feedback")
                .where("feedback", "==", 1)
                .get();

              const likedGames: string[] = [];
              likesSnapshot.forEach((doc) => {
                likedGames.push(doc.id);
              });

              // Fetch all liked game embeddings
              const likedEmbeddings: number[][] = [];
              for (const gameId of likedGames) {
                try {
                  const vec = await index.fetch([gameId]);
                  const embedding = vec.records[gameId]?.values;
                  if (embedding) {
                    likedEmbeddings.push(embedding as number[]);
                  }
                } catch (err) {
                  logger.warn(`Failed to fetch embedding for ${gameId}`, err);
                }
              }

              // Compute average embedding (user profile)
              if (likedEmbeddings.length > 0) {
                const avgEmbedding = likedEmbeddings[0].map((_, i) =>
                  likedEmbeddings.reduce((sum, emb) => sum + emb[i], 0) / likedEmbeddings.length
                );

                // Save to Firestore
                await db
                  .collection("users")
                  .doc(user_id)
                  .set({
                    profile_embedding: avgEmbedding,
                    updated_at: admin.firestore.FieldValue.serverTimestamp(),
                  }, {merge: true});

                logger.info(`Updated profile embedding for user: ${user_id}`);
              }
            }
          } catch (error) {
            logger.error("Error updating profile embedding:", error);
          }
        }
      }

      res.json({
        success: true,
        message: "Feedback submitted successfully",
      });
    } catch (error) {
      logger.error("Error in submitFeedback:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);

/**
 * Cloud Function 4: Get Recommendation Queue
 * Returns personalized game recommendations for a user
 */
export const getQueue = onRequest(
  {cors: true},
  async (req, res) => {
    try {
      logger.info("Getting queue", {body: req.body});

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

      // Get user profile
      const userDoc = await db.collection("users").doc(user_id).get();
      const userData = userDoc.data();
      const profileEmbedding = userData?.profile_embedding;

      let recommendedGames: any[] = [];

      if (!profileEmbedding || profileEmbedding.length === 0) {
        // No profile yet - return popular games
        logger.info("No user profile found, returning popular games");

        const popularSnapshot = await db
          .collection("games")
          .where("has_embedding", "==", true)
          .orderBy("visits", "desc")
          .limit(limit)
          .get();

        popularSnapshot.forEach((doc) => {
          const game = doc.data();
          recommendedGames.push({
            universe_id: doc.id,
            ...game,
          });
        });
      } else {
        // Query Pinecone for similar games
        logger.info("Querying Pinecone for recommendations");

        const index = pc.index("roblox-games");
        const queryResponse = await index.query({
          vector: profileEmbedding,
          topK: limit + 20,
          includeMetadata: true,
        });

        // Get user's feedback to filter out seen/disliked games
        const feedbackSnapshot = await db
          .collection("users")
          .doc(user_id)
          .collection("feedback")
          .get();

        const seenGames = new Set<string>();
        const dislikedGames = new Set<string>();

        feedbackSnapshot.forEach((doc) => {
          const feedback = doc.data().feedback;
          if (feedback === -1) {
            dislikedGames.add(doc.id);
          }
          seenGames.add(doc.id);
        });

        // Filter and fetch game details
        const matches = queryResponse.matches || [];
        for (const match of matches) {
          if (recommendedGames.length >= limit) break;

          const gameId = match.id;

          // Skip seen or disliked games
          if (dislikedGames.has(gameId)) continue;

          // Fetch full game data from Firestore
          const gameDoc = await db.collection("games").doc(gameId).get();
          if (gameDoc.exists) {
            recommendedGames.push({
              universe_id: gameId,
              ...gameDoc.data(),
              score: match.score,
            });
          }
        }
      }

      res.json({
        success: true,
        games: recommendedGames,
        count: recommendedGames.length,
      });
    } catch (error) {
      logger.error("Error in getQueue:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);

/**
 * Cloud Function 5: Reset User Profile
 * Clears user feedback and profile embedding
 */
export const resetUserProfile = onRequest(
  {cors: true},
  async (req, res) => {
    try {
      const {user_id} = req.body;

      if (!user_id) {
        res.status(400).json({error: "Missing required field: user_id"});
        return;
      }

      // Delete all feedback
      const feedbackSnapshot = await db
        .collection("users")
        .doc(user_id)
        .collection("feedback")
        .get();

      const batch = db.batch();
      feedbackSnapshot.forEach((doc) => {
        batch.delete(doc.ref);
      });
      await batch.commit();

      // Reset user profile
      await db.collection("users").doc(user_id).set({
        profile_embedding: [],
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      }, {merge: true});

      logger.info(`Reset profile for user: ${user_id}`);

      res.json({
        success: true,
        message: "User profile reset successfully",
      });
    } catch (error) {
      logger.error("Error in resetUserProfile:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);

/**
 * Cloud Function 6: Get Stats (Optional Admin Tool)
 */
export const getStats = onRequest(
  {cors: true},
  async (req, res) => {
    try {
      const gamesSnapshot = await db.collection("games").get();
      const gamesWithEmbeddings = gamesSnapshot.docs.filter(
        (doc) => doc.data().has_embedding === true
      ).length;

      const usersSnapshot = await db.collection("users").get();

      res.json({
        success: true,
        stats: {
          total_games: gamesSnapshot.size,
          games_with_embeddings: gamesWithEmbeddings,
          total_users: usersSnapshot.size,
        },
      });
    } catch (error) {
      logger.error("Error in getStats:", error);
      res.status(500).json({error: "Internal server error"});
    }
  }
);
