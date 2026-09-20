from redis import Redis
from rq import Worker, Queue
from services.model_training.config import settings

def main():
    redis = Redis.from_url(settings.redis_url)
    worker = Worker([Queue(settings.default_queue, connection=redis)], connection=redis)
    worker.work(with_scheduler=True)

if __name__ == '__main__':
    main()
