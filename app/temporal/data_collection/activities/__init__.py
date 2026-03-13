from app.temporal.data_collection.activities.facebook import collect_facebook
from app.temporal.data_collection.activities.instagram import collect_instagram_hashtags, collect_instagram_posts
from app.temporal.data_collection.activities.twitter import collect_twitter
from app.temporal.data_collection.activities.reddit import collect_reddit
from app.temporal.data_collection.activities.google_news import collect_google_news
from app.temporal.data_collection.activities.youtube import collect_youtube
from app.temporal.data_collection.activities.linkedin import collect_linkedin
from app.temporal.data_collection.activities.meta_ads import collect_meta_ads
from app.temporal.data_collection.activities.ai_classification import classify_collected_data
from app.temporal.data_collection.activities.news_insights import extract_news_insights

ALL_COLLECTION_ACTIVITIES = [
    collect_facebook,
    collect_instagram_hashtags,
    collect_instagram_posts,
    collect_twitter,
    collect_reddit,
    collect_google_news,
    collect_youtube,
    collect_linkedin,
    collect_meta_ads,
    classify_collected_data,
    extract_news_insights,
]
