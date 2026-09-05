import { Redirect } from 'expo-router'

/** The launch route. The gate in the root layout decides where to go. */
export default function Index() {
  return <Redirect href="/(tabs)/home" />
}
