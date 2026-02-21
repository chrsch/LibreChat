/**
 * WebDAV XML response parser.
 *
 * Parses the `207 Multi-Status` XML responses from PROPFIND requests
 * into typed WebDavResponse objects.
 */

import { XMLParser } from 'fast-xml-parser';
import type { WebDavResponse } from '../types.js';

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  removeNSPrefix: true,
  isArray: (name) => name === 'response',
});

/**
 * Parse a WebDAV multistatus XML response into an array of WebDavResponse objects.
 */
export function parseMultiStatus(xml: string): WebDavResponse[] {
  const parsed = parser.parse(xml);

  const multistatus = parsed?.multistatus;
  if (!multistatus) {
    return [];
  }

  const responses = Array.isArray(multistatus.response)
    ? multistatus.response
    : multistatus.response
      ? [multistatus.response]
      : [];

  return responses.map((resp: Record<string, unknown>): WebDavResponse => {
    const href = String(resp.href ?? '');
    const propstat = resp.propstat as Record<string, unknown> | Record<string, unknown>[] | undefined;

    // propstat can be a single object or an array; take the successful one
    let props: Record<string, unknown> = {};
    if (Array.isArray(propstat)) {
      const ok = propstat.find(
        (ps) => String((ps as Record<string, unknown>).status ?? '').includes('200'),
      );
      props = ((ok as Record<string, unknown>)?.prop ?? {}) as Record<string, unknown>;
    } else if (propstat) {
      props = (propstat.prop ?? {}) as Record<string, unknown>;
    }

    const resourcetype = props.resourcetype;
    const isFolder =
      resourcetype != null &&
      typeof resourcetype === 'object' &&
      'collection' in (resourcetype as Record<string, unknown>);

    const etag = String(props.getetag ?? '').replace(/"/g, '');

    return {
      href: decodeURIComponent(href),
      displayname: String(props.displayname ?? ''),
      contentlength: parseInt(String(props.getcontentlength ?? '0'), 10) || 0,
      lastmodified: String(props.getlastmodified ?? ''),
      contenttype: String(props.getcontenttype ?? ''),
      resourcetype: isFolder ? 'folder' : 'file',
      etag,
    };
  });
}
