// Deleting an account (App Store guideline 5.1.1(v)): the user's photos,
// other people's reply photos on the user's posts, then the auth user, which
// removes every row that belongs to them (profile, scans, posts, replies,
// likes, saves, reports, blocks, device tokens) through ON DELETE CASCADE.

export interface AccountStore {
  /** Every photo path in the user's own folder. */
  listOwnPhotos(userId: string): Promise<string[]>;
  /** Reply photos under the user's posts (in other people's folders). */
  replyPhotosOnPostsOf(userId: string): Promise<string[]>;
  removePhotos(paths: string[]): Promise<void>;
  deleteUser(userId: string): Promise<void>;
}

const USER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Deletes the account and returns how many photos were removed. */
export async function deleteAccount(userId: string, store: AccountStore): Promise<number> {
  if (!USER_ID.test(userId)) throw new Error("Unexpected user id");
  const paths = [...new Set([...await store.listOwnPhotos(userId), ...await store.replyPhotosOnPostsOf(userId)])];
  // Photos first: once the rows are gone, nothing points at them any more.
  for (let start = 0; start < paths.length; start += 100) {
    await store.removePhotos(paths.slice(start, start + 100));
  }
  await store.deleteUser(userId);
  return paths.length;
}
