from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "news_letter_subscriptions" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "email" VARCHAR(255) NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS "idx_news_letter_email_82ce14" ON "news_letter_subscriptions" ("email");
CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "username" VARCHAR(255) NOT NULL UNIQUE,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "password" VARCHAR(512),
    "is_active" BOOL NOT NULL DEFAULT False,
    "role" SMALLINT NOT NULL DEFAULT 1,
    "auth_provider" VARCHAR(9) NOT NULL DEFAULT 'internal'
);
CREATE INDEX IF NOT EXISTS "idx_users_usernam_266d85" ON "users" ("username");
CREATE INDEX IF NOT EXISTS "idx_users_email_133a6f" ON "users" ("email");
COMMENT ON COLUMN "users"."auth_provider" IS 'INTERNAL: internal\nGOOGLE: google\nMICROSOFT: microsoft\nMETA: meta';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmFtv2jAUgP9KlKdO6qpC730LHW2ZgEyQblMvikxiglXHzmynF1X899kmIRcIox29TO"
    "ONnEvs8534nGOezJD6EPOtLrznbSgEZP14wD2GIoEo4Q4YYGgeG08mAaH6sZT9pmGCKMqs"
    "lUAkbzKJ9HSxdnV53le7DbhgwBPScAgwh1Lkw6mJlJIYYyWknjREJMhEMUG/YugKGkAxgk"
    "wqrm6kGBEfPkCePka37hBB7BdiQr5aW8td8RhpWYuIU22oVhu4HsVxSDLj6FGMKJlaIyKU"
    "NIAEMiCger1gsdq+2l0SehrRZKeZyWSLOR8fDkGMRS7cJRl4EqPkJ3fDdYCBWuVzvbZ7sH"
    "u4s797KE30TqaSg/EkvCz2iaMm0HXMsdYDASYWGmPGzWNQBesCMcvvi9QIFML5EIueJZh+"
    "4rqV/iijTUEuYpsKMrjZB7UiujIG3yb4MUncApROq9PsO1bnm4ok5PwX1ogsp6k0dS19LE"
    "k39j8pOZXHYXJwpi8xfrScc0M9Gpd2t6kJUi4CplfM7JxLU+0JxIK6hN67wM99Y6k0BSMt"
    "s8TGkf/CxBY914l918Qmm8/yCkOA8GxKT0aAzU/n1KGUSYnrJbl79YIXggfZW0ggRqrK7e"
    "0tSN13q3dybvU2pFUpH91EVZ/oxmPVOIa3uRKoBAPg3d4D5rszGlqnVbazqrAeliWAgEDT"
    "UUGqCJKee8Ehq+7IOe3C/hsru3WvXffadUle99p1Yl+t16o6q38/o93mff7rjrseWlaKMA"
    "Kc31M2p/VWU8z7vAhkgukti0mB5F6tvgRJaVVJUuuKJBF35ciE7uYc6walGAJSMcnk/Uo4"
    "B9Lxtarzcye7EtEFABu23S5U4kbLKYG86DSavY2a5iuNkID5WSeDyiiew7MfAowrR8PU58"
    "/D4apQ1v56ONypH+xP50L1sGgk7HesdnuWlWw5Izdi9A75kM0/z00ShxpaS24CEA/OwJt5"
    "yWoq5TIUVYZUk9NffBGn+jKava7VPjZSo2tyZttn7eaxEVAaYHhNOq2Tnt23T51jI0Qeo5"
    "wOhZQ2HUsKoADmCyrF0RJ14qiyShx9oCuiBRnyRuac62Gi2Vx0NQSZzfpuuMq+9Mp3wzt5"
    "o1dbekZ3z7m83dn/8HOSOhrPgJiY/5sAa9vbSwCUVpUAta4IUK4oIJlzk/3at7sVf09kLi"
    "WQF0QGeOUjT2waGHFx8zGxLqCooi7MSCm8jY71s8z1pG03ytdQ9YLGe7eX8W9gBAK/"
)
