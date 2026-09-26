import { assertEquals, assertRejects } from "jsr:@std/assert@1.0.14";
import { type AccountStore, deleteAccount } from "./account.ts";

const user = "6b1f2c8e-2d4a-4e61-9b4b-0a1d7e3c5f01";

function fakeStore(own: string[], replies: string[]) {
  const steps: string[] = [];
  const store: AccountStore = {
    listOwnPhotos: () => Promise.resolve(own),
    replyPhotosOnPostsOf: () => Promise.resolve(replies),
    removePhotos: (paths) => { steps.push(`remove ${paths.length}`); return Promise.resolve(); },
    deleteUser: (id) => { steps.push(`delete ${id}`); return Promise.resolve(); },
  };
  return { store, steps };
}

Deno.test("photos go first, then the account", async () => {
  const { store, steps } = fakeStore([`${user}/a.jpg`, `${user}/b.jpg`], ["other/c.jpg", `${user}/a.jpg`]);
  assertEquals(await deleteAccount(user, store), 3);
  assertEquals(steps, ["remove 3", `delete ${user}`]);
});

Deno.test("many photos are removed in batches of 100", async () => {
  const own = Array.from({ length: 250 }, (_, i) => `${user}/${i}.jpg`);
  const { store, steps } = fakeStore(own, []);
  await deleteAccount(user, store);
  assertEquals(steps, ["remove 100", "remove 100", "remove 50", `delete ${user}`]);
});

Deno.test("an account without photos is just deleted", async () => {
  const { store, steps } = fakeStore([], []);
  assertEquals(await deleteAccount(user, store), 0);
  assertEquals(steps, [`delete ${user}`]);
});

Deno.test("only real user ids are accepted", async () => {
  const { store } = fakeStore([], []);
  await assertRejects(() => deleteAccount("../../etc", store), Error, "Unexpected user id");
});
